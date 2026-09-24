"""
Saleha Agents: Base Agent (v3.1 - Model Provider Abstraction)

Naya vs pehle: Ollama se seedha baat karne ke bajaye ab `model_provider.py`
ke through hota hai. Behavior bilkul same hai (same URL, same payload,
same timeout) -- sirf ye ki agar kabhi backend badalna ho, sirf
model_provider.py me naya provider likhna hoga, ye file chhedni nahi padegi.
"""
import os
import uuid
import time
from dataclasses import dataclass
from typing import Any, Optional

from saleha.core.platform.model_provider import default_provider, MockProvider, ModelProvider


@dataclass
class AgentResponse:
    success: bool
    content: str
    error_message: str = ""
    model_used: str = ""
    response_time: float = 0.0
    tokens_used: int = 0
    # >0 when the prompt exceeded the model's context budget and was trimmed
    # before the call. Silent truncation by the runtime is invisible; this is
    # not. A caller that cares about completeness can check it.
    context_trimmed_chars: int = 0


class BaseAgent:
    def __init__(
        self,
        role: str,
        model: str = "auto",
        provider: Optional[ModelProvider] = None,
        **kwargs: Any,
    ):
        self.role = role
        self.model_preference = model
        # Under SALEHA_TEST_MODE, any agent constructed without an explicit
        # provider AND without model="mock" gets the fast in-process
        # MockProvider instead of the real Ollama/OpenAI-compatible fallback
        # chain. A caller that passes `provider=` (a real integration test)
        # still overrides it below, unconditionally.
        if (provider is None and model != "mock"
                and os.environ.get("SALEHA_TEST_MODE") == "1"):
            self.provider: ModelProvider = MockProvider()
        else:
            self.provider = provider or default_provider  # naya: pluggable backend
        self.task_counter = 0
        # "auto" mode me runtime Ollama probing enable -- router sirf installed
        # models choose karta hai (2026 catalog + adaptive candidate filtering).
        if model == "auto":
            from saleha.core.platform.smart_router import SmartRouter
            self.router = SmartRouter(probe_runtime=True)
        else:
            self.router = None
        self.total_tokens_used = 0  # v1.2: agent-lifetime token accounting
        # Sampling temperature for think(); None keeps the provider default.
        # Was only ever set ad hoc via setattr/getattr.
        self.temperature: Optional[float] = kwargs.get("temperature")

        # Agent Personal Computer (AgentPC): Dedicated workspace, hardware sandbox & blackbox
        from saleha.core.agent_pc import get_agent_pc
        self.pc = get_agent_pc(
            agent_role=self.role,
            base_dir=kwargs.get("pc_workspace_dir"),
        )

    def _record_tokens(self, provider_result) -> int:
        used = int(getattr(provider_result, "tokens_used", 0) or 0)
        self.total_tokens_used += used
        return used

    def think(self, prompt: str, previous_error_reflexion: Optional[str] = None,
              complexity_score: float = 0.0,
              disable_reasoning: bool = False,
              **kwargs: Any) -> AgentResponse:
        self.task_counter += 1
        start_time = time.time()

        # Smart model selection
        if self.model_preference == "auto" and self.router:
            selected_model = self.router.select_model(prompt, complexity_score)
        else:
            selected_model = self.model_preference

        unique_task_id = f"TASK-{uuid.uuid4().hex[:8]}-{self.task_counter}"
        full_prompt = f"[UNIQUE TASK ID: {unique_task_id}]\n\n{prompt}"
        if previous_error_reflexion:
            full_prompt += f"\n\n[SALEHA SELF-HEALING INSTRUCTION]:\n{previous_error_reflexion}"

        # Context budget guard. Measured on this box: a 280 KB prompt to
        # qwen2.5-coder:3b returns success=True with the answer silently
        # dropped -- Ollama cuts the middle without an error, and nothing
        # downstream can tell that from a real answer. Four agents (coder,
        # debugger, qa_lead, reviewer) interpolate {code} with no bound, so
        # the guard lives here, at the one chokepoint they all pass through.
        # Trimming is visible in the prompt and recorded on the response.
        context_trimmed_chars = 0
        try:
            from saleha.core.context_budget import fit

            fitted, budget = fit(full_prompt, selected_model,
                                 reserve_output_tokens=1024)
            if budget.trimmed:
                context_trimmed_chars = budget.trimmed_chars
                print(f"  [{self.role}] Prompt exceeded the context budget; "
                      f"trimmed {budget.trimmed_chars} chars from the middle "
                      f"({budget.describe()}).")
                full_prompt = fitted
        except Exception:
            # A guard that breaks the call it is guarding is worse than no
            # guard: fall through with the original prompt.
            context_trimmed_chars = 0

        temp = getattr(self, "temperature", None)
        options = {"temperature": temp} if temp is not None else None
        provider_result = self.provider.generate(
            model=selected_model, prompt=full_prompt, options=options,
            disable_reasoning=disable_reasoning)
        response_time = provider_result.response_time or (time.time() - start_time)

        if self.router:
            self.router.record_result(
                prompt, complexity_score, selected_model,
                response_time, provider_result.success
            )

        tokens_used = self._record_tokens(provider_result)
        self.pc.blackbox.record(
            event_type="THINK",
            stage="LLM_INFERENCE",
            payload={
                "task_id": unique_task_id,
                "model_used": selected_model,
                "success": provider_result.success,
                "response_time": response_time,
                "tokens_used": tokens_used,
            },
            status="SUCCESS" if provider_result.success else "FAILED",
        )

        if provider_result.success:
            return AgentResponse(
                success=True,
                content=provider_result.content,
                model_used=selected_model,
                response_time=response_time,
                tokens_used=tokens_used,
                context_trimmed_chars=context_trimmed_chars,
            )
        else:
            return AgentResponse(
                success=False,
                content="",
                error_message=provider_result.error_message,
                model_used=selected_model,
                response_time=response_time,
                context_trimmed_chars=context_trimmed_chars,
            )

    def think_stream(self, prompt: str, on_token=None,
                     previous_error_reflexion: Optional[str] = None,
                     complexity_score: float = 0.0) -> AgentResponse:
        """Token-level real-time streaming variant of think().

        `on_token(str)` har token chunk par fire hota hai (Ollama NDJSON
        stream). Response poora hoke wahi AgentResponse milti hai -- callers
        tokens live print kar sakte hain bina downstream logic badle.

        Provider stream support na kare to silently non-streaming generate
        pe fallback (graceful degradation).
        """
        self.task_counter += 1
        start_time = time.time()

        if self.model_preference == "auto" and self.router:
            selected_model = self.router.select_model(prompt, complexity_score)
        else:
            selected_model = self.model_preference

        unique_task_id = f"TASK-{uuid.uuid4().hex[:8]}-{self.task_counter}"
        full_prompt = f"[UNIQUE TASK ID: {unique_task_id}]\n\n{prompt}"
        if previous_error_reflexion:
            full_prompt += f"\n\n[SALEHA SELF-HEALING INSTRUCTION]:\n{previous_error_reflexion}"

        stream_fn = getattr(self.provider, "stream_generate", None)
        if callable(stream_fn):
            stream_temp = getattr(self, "temperature", None)
            stream_opts = {"temperature": stream_temp} if stream_temp is not None else None
            provider_result = stream_fn(model=selected_model, prompt=full_prompt,
                                        callback=on_token, options=stream_opts)
        else:
            # Profile-set temperature ho to provider options me jao (v1.4 wiring);
            # warna provider apne defaults use karta hai.
            temp = getattr(self, "temperature", None)
            options = {"temperature": temp} if temp is not None else None
            provider_result = self.provider.generate(model=selected_model, prompt=full_prompt, options=options)

        response_time = provider_result.response_time or (time.time() - start_time)

        if self.router:
            self.router.record_result(
                prompt, complexity_score, selected_model,
                response_time, provider_result.success
            )

        tokens_used = self._record_tokens(provider_result)
        self.pc.blackbox.record(
            event_type="THINK_STREAM",
            stage="LLM_INFERENCE",
            payload={
                "task_id": unique_task_id,
                "model_used": selected_model,
                "success": provider_result.success,
                "response_time": response_time,
                "tokens_used": tokens_used,
            },
            status="SUCCESS" if provider_result.success else "FAILED",
        )

        if provider_result.success:
            return AgentResponse(
                success=True,
                content=provider_result.content,
                model_used=selected_model,
                response_time=response_time,
                tokens_used=tokens_used,
            )
        return AgentResponse(
            success=False,
            content="",
            error_message=provider_result.error_message,
            model_used=selected_model,
            response_time=response_time,
        )

    def run_in_pc(
        self,
        code: str,
        filename: str = "task.py",
        verify_ast: bool = True,
        timeout_sec: Optional[float] = None,
    ):
        """Runs Python code inside this agent's isolated personal computer sandbox."""
        return self.pc.execute_code(
            code=code,
            filename=filename,
            verify_ast=verify_ast,
            timeout_sec=timeout_sec,
        )

    def write_in_pc(self, rel_path: str, content: str) -> Any:
        """Writes a file inside this agent's isolated PC workspace."""
        path = self.pc.workspace.write_file(rel_path, content)
        self.pc.blackbox.record(
            event_type="FILE_WRITE",
            stage="WORKSPACE",
            payload={"filename": rel_path, "bytes": len(content)},
            status="WRITTEN",
        )
        return path

    def read_from_pc(self, rel_path: str) -> str:
        """Reads a file from this agent's isolated PC workspace."""
        content = self.pc.workspace.read_file(rel_path)
        self.pc.blackbox.record(
            event_type="FILE_READ",
            stage="WORKSPACE",
            payload={"filename": rel_path, "bytes": len(content)},
            status="READ",
        )
        return content

    def checkpoint_pc(self, tag: str) -> str:
        """Creates a time-travel checkpoint of this agent's PC workspace."""
        chk = self.pc.workspace.create_checkpoint(tag)
        self.pc.blackbox.record(
            event_type="CHECKPOINT",
            stage="SNAPSHOT",
            payload={"checkpoint_id": chk.checkpoint_id, "tag": tag},
            status="CREATED",
        )
        return chk.checkpoint_id

    def restore_pc(self, checkpoint_id_or_tag: str) -> bool:
        """Restores this agent's PC workspace to a previous checkpoint."""
        ok = self.pc.workspace.restore_checkpoint(checkpoint_id_or_tag)
        status = "RESTORED" if ok else "NOT_FOUND"
        self.pc.blackbox.record(
            event_type="RESTORE",
            stage="ROLLBACK",
            payload={"target": checkpoint_id_or_tag, "success": ok},
            status=status,
        )
        return ok

    def export_from_pc(
        self,
        src_relpath: str,
        dest_abspath: Any,
        require_green_run: bool = True,
    ) -> bool:
        """Exports a verified file from this agent's PC to the repository."""
        return self.pc.export_verified_artifact(
            src_relpath=src_relpath,
            dest_abspath=dest_abspath,
            require_green_run=require_green_run,
        )