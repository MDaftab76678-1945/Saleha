"""
Saleha Core: Local LoRA Fine-Tuning Pipeline

Orchestrates the full LoRA fine-tuning lifecycle:
1. Auto-collect training data from Saleha sessions (TrainingCollector).
2. Real LoRA fine-tuning via HuggingFace PEFT + TRL (SFTTrainer) on local GPU/CPU.
3. Merge the adapter into the base model and register it with local Ollama --
   Ollama performs the actual GGUF conversion + quantization internally via
   `ollama create`, so no GGUF bytes are hand-rolled here.
4. Measure real before/after quality: held-out cross-entropy loss always,
   plus a real sandboxed Pass@1 benchmark delta when deployed to Ollama.

100% local, $0 cost. No simulated numbers: if a step can't run for real
(missing deps, insufficient data, unknown base model), fine_tune() reports
success=False with a concrete error instead of fabricating a result.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

from saleha.core.training_collector import TrainingCollector

# Ollama-style short name -> HF repo id, for the base models we know how to
# fine-tune locally (all four are already cached in this environment).
BASE_MODEL_HF_MAP: Dict[str, str] = {
    "qwen2.5-coder:0.5b": "Qwen/Qwen2.5-Coder-0.5B-Instruct",
    "qwen2.5-coder:1.5b": "Qwen/Qwen2.5-Coder-1.5B-Instruct",
    "qwen2.5-coder:3b": "Qwen/Qwen2.5-Coder-3B-Instruct",
    "qwen2.5-coder:7b": "Qwen/Qwen2.5-Coder-7B-Instruct",
}

DEFAULT_TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


def ensure_trl_dpo_importable() -> None:
    """
    Real, verified environment fix (not a hack around correctness): trl's
    DPOTrainer unconditionally imports `FSDPModule` from `torch.distributed.
    fsdp` at module load time (used only inside `prepare_fsdp()`, for real
    multi-GPU FSDP2 training). `FSDPModule` was only moved into that public
    namespace in PyTorch's Dec 2024 "FSDP2 move to public torch.distributed
    .fsdp" change (torch >= 2.6) -- on torch 2.5.1 (installed here, and
    verified to work correctly for everything else: SFT, QLoRA, merging),
    the import raises ImportError before DPOTrainer is even usable, on a
    single-GPU box that would never call prepare_fsdp() anyway.

    Rather than upgrade torch (real risk: would need re-verifying the whole
    already-working CUDA/bitsandbytes/peft stack against a new torch build),
    this defines a placeholder FSDPModule class in that namespace if it's
    missing. It is never actually instantiated or matched against on a
    single-GPU run -- prepare_fsdp() is real code we simply never call.
    Call this before `from trl import DPOTrainer, DPOConfig`.
    """
    import torch.distributed.fsdp as _fsdp_mod
    if not hasattr(_fsdp_mod, "FSDPModule"):
        class FSDPModule:  # noqa: N801 -- matching torch's real (newer) class name
            """Placeholder only: real FSDP2 code never runs on this single-GPU setup."""
            pass
        _fsdp_mod.FSDPModule = FSDPModule

def _find_llama_cpp_converter() -> Optional[str]:
    """
    Locate a local llama.cpp checkout's real convert_hf_to_gguf.py, if one
    is set up. Checked in order: SALEHA_LLAMA_CPP_DIR env var, then
    ~/.saleha/llama.cpp. Returns None if not found -- callers must fall
    back to Ollama's own built-in conversion (verified buggy on this
    platform, see _is_degenerate) rather than fail outright, since not
    every environment will have this set up.
    """
    candidates = []
    env_dir = os.environ.get("SALEHA_LLAMA_CPP_DIR")
    if env_dir:
        candidates.append(env_dir)
    candidates.append(os.path.join(os.path.expanduser("~"), ".saleha", "llama.cpp"))
    for d in candidates:
        script = os.path.join(d, "convert_hf_to_gguf.py")
        if os.path.isfile(script):
            return script
    return None


def _convert_to_gguf_via_llama_cpp(merged_dir: str, out_path: str) -> Optional[str]:
    """
    Real fix for the Ollama GGUF corruption bug documented in
    _is_degenerate()/_verify_ollama_deployment(): verified end-to-end
    (real merged model -> real conversion -> real Ollama import -> real
    generation, checked for degenerate output) that `ollama create`
    importing directly from a raw HF safetensors directory can silently
    produce garbage on this platform even on returncode 0, while
    converting via llama.cpp's own convert_hf_to_gguf.py first and
    importing THAT .gguf into Ollama (`FROM <path>.gguf`) produces
    correct, coherent output instead.

    Returns the produced .gguf path on success, or None if no local
    llama.cpp checkout is configured or the conversion itself failed --
    either way the caller falls back to the direct-safetensors path (worse
    but not silently broken, since _verify_ollama_deployment still gates
    what gets reported as deployed).
    """
    converter = _find_llama_cpp_converter()
    if not converter:
        return None
    try:
        result = subprocess.run(
            [sys.executable, converter, merged_dir, "--outfile", out_path, "--outtype", "f16"],
            cwd=os.path.dirname(converter), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=600,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 or not os.path.exists(out_path):
        return None
    return out_path


# Qwen2.5-Coder's real ChatML template (copied verbatim from `ollama show
# qwen2.5-coder:3b --modelfile`). Ollama's raw-safetensors import does NOT
# reliably pick up a HF chat_template.jinja -- without this, imported models
# fall back to a bare `TEMPLATE {{ .Prompt }}` passthrough with no
# <|im_start|>/<|im_end|> role markers. The base model was never trained to
# respond to that raw format via the chat API, so it produces degenerate,
# repeated-token garbage output (verified: real generations came back as
# literal "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@" once this was missing).
QWEN_CHATML_TEMPLATE = '''"""{{- if .Suffix }}<|fim_prefix|>{{ .Prompt }}<|fim_suffix|>{{ .Suffix }}<|fim_middle|>
{{- else if .Messages }}
{{- if or .System .Tools }}<|im_start|>system
{{- if .System }}
{{ .System }}
{{- end }}
{{- if .Tools }}

# Tools

You may call one or more functions to assist with the user query.

You are provided with function signatures within <tools></tools>:
<tools>
{{- range .Tools }}
{"type": "function", "function": {{ .Function }}}
{{- end }}
</tools>

For each function call, return a json object with function name and arguments within <tool_call></tool_call> with NO other text. Do not include any backticks or ```json.
<tool_call>
{"name": <function-name>, "arguments": <args-json-object>}
</tool_call>
{{- end }}<|im_end|>
{{ end }}
{{- range $i, $_ := .Messages }}
{{- $last := eq (len (slice $.Messages $i)) 1 -}}
{{- if eq .Role "user" }}<|im_start|>user
{{ .Content }}<|im_end|>
{{ else if eq .Role "assistant" }}<|im_start|>assistant
{{ if .Content }}{{ .Content }}
{{- else if .ToolCalls }}<tool_call>
{{ range .ToolCalls }}{"name": "{{ .Function.Name }}", "arguments": {{ .Function.Arguments }}}
{{ end }}</tool_call>
{{- end }}{{ if not $last }}<|im_end|>
{{ end }}
{{- else if eq .Role "tool" }}<|im_start|>user
<tool_response>
{{ .Content }}
</tool_response><|im_end|>
{{ end }}
{{- if and (ne .Role "assistant") $last }}<|im_start|>assistant
{{ end }}
{{- end }}
{{- else }}
{{- if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{ if .Prompt }}<|im_start|>user
{{ .Prompt }}<|im_end|>
{{ end }}<|im_start|>assistant
{{ end }}{{ .Response }}{{ if .Response }}<|im_end|>{{ end }}"""'''


@dataclass
class TuningConfig:
    base_model: str = "qwen2.5-coder:3b"
    lora_rank: int = 16
    lora_alpha: float = 32.0
    learning_rate: float = 2e-4
    epochs: int = 3
    batch_size: int = 4
    max_seq_len: int = 2048
    output_model_name: str = "saleha-custom"
    eval_holdout_frac: float = 0.1
    deploy_to_ollama: bool = True
    run_benchmark: bool = True   # real Pass@1 delta; only attempted if deploy succeeds
    load_in_4bit: Optional[bool] = None  # None = auto (on for 7B+ models, off otherwise)


@dataclass
class TuningResult:
    success: bool
    base_model: str
    output_model: str
    samples_used: int
    training_time_sec: float
    before_score: float = 0.0          # held-out eval loss before training (lower=better)
    after_score: float = 0.0           # held-out eval loss after training
    improvement_pct: float = 0.0       # loss reduction %, computed from real numbers
    error: str = ""
    adapter_path: str = ""
    deployed_to_ollama: bool = False
    benchmark_before_pass_rate: Optional[float] = None
    benchmark_after_pass_rate: Optional[float] = None
    benchmark_error: str = ""


class LoRATuner:
    """
    Manages real local LoRA fine-tuning of Qwen2.5-Coder models via
    HuggingFace PEFT + TRL, with optional deployment to local Ollama and
    real before/after quality measurement.
    """

    def __init__(self, work_dir: str = os.path.join(os.path.expanduser("~"), ".saleha", "lora_work")):
        self.work_dir = work_dir
        os.makedirs(work_dir, exist_ok=True)
        self.collector = TrainingCollector()

    def _detect_backend(self) -> str:
        """Detect whether the real local fine-tuning stack is importable."""
        try:
            import torch  # noqa: F401
            import peft  # noqa: F401
            import trl  # noqa: F401
            import transformers  # noqa: F401
        except ImportError:
            return "unavailable"
        return "transformers_peft"

    def _resolve_hf_base(self, base_model: str) -> str:
        if base_model in BASE_MODEL_HF_MAP:
            return BASE_MODEL_HF_MAP[base_model]
        if "/" in base_model:  # already looks like an HF repo id
            return base_model
        raise ValueError(
            f"Unknown base model '{base_model}'. Known local models: "
            f"{list(BASE_MODEL_HF_MAP)}. Pass a full HF repo id to use another model."
        )

    def prepare_dataset(self, min_quality: float = 0.75, format: str = "alpaca") -> Optional[str]:
        """Prepare training dataset from collected samples."""
        samples = self.collector.load_samples(min_quality=min_quality)
        if not samples:
            return None
        out_path = os.path.join(self.work_dir, f"train_data.{'json' if format == 'alpaca' else 'jsonl'}")
        if format == "alpaca":
            self.collector.export_alpaca(out_path, min_quality=min_quality)
        else:
            self.collector.export_sharegpt(out_path, min_quality=min_quality)
        return out_path

    def tune(self, config: Optional[TuningConfig] = None) -> TuningResult:
        """Alias for fine_tune (kept for callers/tests using the shorter name)."""
        return self.fine_tune(config)

    def tune_dpo(self, dpo_dataset_path: str = "datasets/saleha_dpo_pairs.jsonl",
                 config: Optional[TuningConfig] = None) -> TuningResult:
        """
        Real DPO fine-tuning via trl.DPOTrainer on chosen/rejected preference
        pairs. Replaces a prior fabricated version of this method (fixed
        76.5->92.4 hardcoded scores, `time.sleep(0.15)` standing in for
        training) -- if DPO can't actually run here (missing/incompatible
        trl/torch, no real data), this reports success=False with the real
        error instead of a fake result.
        """
        cfg = config or TuningConfig(output_model_name="saleha-dpo-slm")
        start_t = time.time()

        dpo_count = 0
        if os.path.exists(dpo_dataset_path):
            with open(dpo_dataset_path, "r", encoding="utf-8") as f:
                dpo_count = sum(1 for line in f if line.strip())

        if dpo_count == 0:
            from saleha.core.dpo_dataset_engine import dpo_dataset_engine
            dpo_count, _ = dpo_dataset_engine.build_dataset(target_count=100)
            dpo_dataset_path = dpo_dataset_engine.export_dpo_jsonl()

        if dpo_count == 0:
            return TuningResult(
                success=False, base_model=cfg.base_model, output_model=cfg.output_model_name,
                samples_used=0, training_time_sec=round(time.time() - start_t, 2),
                error="No DPO preference pairs available (dataset empty and synthesis produced none)."
            )

        backend = self._detect_backend()
        if backend == "unavailable":
            return TuningResult(
                success=False, base_model=cfg.base_model, output_model=cfg.output_model_name,
                samples_used=dpo_count, training_time_sec=round(time.time() - start_t, 2),
                error="No local fine-tuning backend available. Install: "
                      "pip install torch peft trl transformers accelerate"
            )

        adapter_path = os.path.join(self.work_dir, f"{cfg.output_model_name}_dpo_adapter")
        try:
            data = self._train_dpo(cfg, dpo_dataset_path, adapter_path)
            elapsed = round(time.time() - start_t, 2)
            return TuningResult(
                success=True, base_model=cfg.base_model, output_model=cfg.output_model_name,
                samples_used=dpo_count, training_time_sec=elapsed,
                before_score=data["before_score"], after_score=data["after_score"],
                improvement_pct=data["improvement_pct"], adapter_path=adapter_path,
            )
        except Exception as e:
            return TuningResult(
                success=False, base_model=cfg.base_model, output_model=cfg.output_model_name,
                samples_used=dpo_count, training_time_sec=round(time.time() - start_t, 2), error=str(e)
            )

    def _train_dpo(self, config: TuningConfig, dataset_path: str, adapter_path: str) -> Dict[str, Any]:
        """Real DPO training via trl.DPOTrainer, fresh LoRA on the base model."""
        import torch
        from datasets import load_dataset
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import LoraConfig
        ensure_trl_dpo_importable()
        from trl import DPOTrainer, DPOConfig

        hf_base = self._resolve_hf_base(config.base_model)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if device == "cuda" else torch.float32

        tokenizer = AutoTokenizer.from_pretrained(hf_base)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        model = AutoModelForCausalLM.from_pretrained(hf_base, dtype=dtype, device_map=device)
        lora_config = LoraConfig(
            r=config.lora_rank, lora_alpha=int(config.lora_alpha),
            target_modules=DEFAULT_TARGET_MODULES, lora_dropout=0.05,
            bias="none", task_type="CAUSAL_LM",
        )

        dataset = load_dataset("json", data_files=dataset_path, split="train")
        if len(dataset) >= 10:
            split = dataset.train_test_split(test_size=0.1, seed=42)
            train_ds, eval_ds = split["train"], split["test"]
        else:
            train_ds, eval_ds = dataset, dataset

        dpo_config = DPOConfig(
            output_dir=os.path.join(self.work_dir, f"{config.output_model_name}_dpo_run"),
            num_train_epochs=1, per_device_train_batch_size=1, learning_rate=5e-6,
            logging_steps=10, save_strategy="no", report_to=[], bf16=(device == "cuda"),
        )
        trainer = DPOTrainer(
            model=model, args=dpo_config, train_dataset=train_ds, eval_dataset=eval_ds,
            processing_class=tokenizer, peft_config=lora_config,
        )
        before_metrics = trainer.evaluate()
        trainer.train()
        after_metrics = trainer.evaluate()

        os.makedirs(adapter_path, exist_ok=True)
        trainer.model.save_pretrained(adapter_path)
        tokenizer.save_pretrained(adapter_path)

        before_loss = before_metrics.get("eval_loss", 0.0)
        after_loss = after_metrics.get("eval_loss", 0.0)
        improvement_pct = round((before_loss - after_loss) / before_loss * 100, 2) if before_loss else 0.0
        return {"before_score": round(before_loss, 4), "after_score": round(after_loss, 4),
                "improvement_pct": improvement_pct}

    def fine_tune(self, config: Optional[TuningConfig] = None) -> TuningResult:
        """Execute the full local LoRA fine-tuning pipeline. No fabricated results."""
        cfg = config or TuningConfig()
        start_t = time.time()

        samples = self.collector.load_samples(min_quality=0.75)
        if len(samples) < 5:
            return TuningResult(
                success=False, base_model=cfg.base_model, output_model=cfg.output_model_name,
                samples_used=0, training_time_sec=0.0,
                error=f"Insufficient training data: {len(samples)} samples (need >=5). "
                      "Run 'saleha run' tasks to collect more samples, or add samples via "
                      "TrainingCollector.add_sample()."
            )

        dataset_path = self.prepare_dataset(format="alpaca")
        if not dataset_path:
            return TuningResult(
                success=False, base_model=cfg.base_model, output_model=cfg.output_model_name,
                samples_used=0, training_time_sec=0.0, error="Failed to prepare dataset."
            )

        backend = self._detect_backend()
        if backend == "unavailable":
            return TuningResult(
                success=False, base_model=cfg.base_model, output_model=cfg.output_model_name,
                samples_used=len(samples), training_time_sec=round(time.time() - start_t, 2),
                error="No local fine-tuning backend available. Install: "
                      "pip install torch peft trl transformers accelerate"
            )

        adapter_path = os.path.join(self.work_dir, f"{cfg.output_model_name}_lora")
        try:
            data = self._train_transformers_peft(cfg, dataset_path, adapter_path)
            elapsed = round(time.time() - start_t, 2)
            return TuningResult(
                success=True,
                base_model=cfg.base_model,
                output_model=cfg.output_model_name,
                samples_used=len(samples),
                training_time_sec=elapsed,
                before_score=data["before_score"],
                after_score=data["after_score"],
                improvement_pct=data["improvement_pct"],
                adapter_path=adapter_path,
                deployed_to_ollama=data["deployed_to_ollama"],
                benchmark_before_pass_rate=data.get("benchmark_before_pass_rate"),
                benchmark_after_pass_rate=data.get("benchmark_after_pass_rate"),
                benchmark_error=data.get("benchmark_error", ""),
            )
        except Exception as e:
            return TuningResult(
                success=False, base_model=cfg.base_model, output_model=cfg.output_model_name,
                samples_used=len(samples), training_time_sec=round(time.time() - start_t, 2),
                error=str(e)
            )

    def _train_transformers_peft(self, config: TuningConfig, dataset_path: str,
                                  adapter_path: str) -> Dict[str, Any]:
        """Real LoRA SFT via HuggingFace PEFT + TRL on local GPU/CPU.
        Uses real QLoRA (4-bit NF4 quantized base + bitsandbytes) for 7B+
        models so they fit in 6GB VRAM -- auto-detected from the model name
        unless config.load_in_4bit forces it explicitly."""
        import torch
        from datasets import load_dataset
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import LoraConfig, prepare_model_for_kbit_training
        from trl import SFTTrainer, SFTConfig

        hf_base = self._resolve_hf_base(config.base_model)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if device == "cuda" else torch.float32

        use_4bit = config.load_in_4bit
        if use_4bit is None:
            import re
            size_match = re.search(r"(\d+(?:\.\d+)?)b", config.base_model.lower())
            use_4bit = bool(size_match and float(size_match.group(1)) >= 7) and device == "cuda"

        quant_config = None
        if use_4bit:
            from transformers import BitsAndBytesConfig
            quant_config = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=dtype, bnb_4bit_use_double_quant=True,
            )

        tokenizer = AutoTokenizer.from_pretrained(hf_base)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        def to_text(example: Dict[str, str]) -> str:
            user_content = example["instruction"]
            if example.get("input"):
                user_content += "\n\n" + example["input"]
            msgs = [
                {"role": "user", "content": user_content},
                {"role": "assistant", "content": example["output"]},
            ]
            return tokenizer.apply_chat_template(msgs, tokenize=False)

        raw = load_dataset("json", data_files=dataset_path, split="train")
        if len(raw) >= 10:
            split = raw.train_test_split(test_size=max(0.05, min(0.3, config.eval_holdout_frac)), seed=42)
            train_ds, eval_ds = split["train"], split["test"]
        else:
            # Too few samples for a genuine holdout -- train and eval on the
            # same tiny set. The reported before/after delta is then a weaker
            # (train-fit) signal, not a true generalization measurement.
            train_ds, eval_ds = raw, raw

        model = AutoModelForCausalLM.from_pretrained(
            hf_base, dtype=dtype, device_map=device, quantization_config=quant_config,
        )
        if use_4bit:
            model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)

        before_loss = self._eval_loss(model, tokenizer, eval_ds, to_text)

        lora_config = LoraConfig(
            r=config.lora_rank, lora_alpha=int(config.lora_alpha),
            target_modules=DEFAULT_TARGET_MODULES, lora_dropout=0.05,
            bias="none", task_type="CAUSAL_LM",
        )

        sft_config = SFTConfig(
            output_dir=os.path.join(self.work_dir, f"{config.output_model_name}_run"),
            num_train_epochs=config.epochs,
            per_device_train_batch_size=max(1, config.batch_size),
            learning_rate=config.learning_rate,
            max_length=config.max_seq_len,
            logging_steps=5,
            save_strategy="no",
            report_to=[],
            bf16=(device == "cuda"),
            packing=False,
            dataset_text_field="text",
        )

        train_ds = train_ds.map(lambda ex: {"text": to_text(ex)})

        trainer = SFTTrainer(
            model=model,
            args=sft_config,
            train_dataset=train_ds,
            peft_config=lora_config,
        )
        trainer.train()

        trained_model = trainer.model
        after_loss = self._eval_loss(trained_model, tokenizer, eval_ds, to_text)

        os.makedirs(adapter_path, exist_ok=True)
        trained_model.save_pretrained(adapter_path)
        tokenizer.save_pretrained(adapter_path)

        improvement_pct = round((before_loss - after_loss) / before_loss * 100, 2) if before_loss > 0 else 0.0

        result: Dict[str, Any] = {
            "before_score": round(before_loss, 4),
            "after_score": round(after_loss, 4),
            "improvement_pct": improvement_pct,
            "deployed_to_ollama": False,
        }

        if config.deploy_to_ollama:
            # Free training-time GPU memory before loading base+adapter again to merge.
            del trainer, trained_model, model
            torch.cuda.empty_cache() if device == "cuda" else None

            deployed = self.register_with_ollama(config.output_model_name, adapter_path, hf_base_model=hf_base)
            result["deployed_to_ollama"] = deployed

            if deployed and config.run_benchmark:
                try:
                    result["benchmark_before_pass_rate"], result["benchmark_after_pass_rate"] = \
                        self._run_isolated_benchmark(config.base_model, config.output_model_name)
                except Exception as e:
                    result["benchmark_error"] = str(e)

        return result

    @staticmethod
    def _is_degenerate(text: str) -> bool:
        """
        Real, cheap check for a known Ollama-conversion failure mode
        (verified reproducible on this platform: a correctly-merged model
        that generates fine via plain HuggingFace/transformers can come out
        of `ollama create`'s GGUF conversion producing pure repeated-token
        garbage, e.g. "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@", at every
        quantization level -- q4 default and explicit f16 both reproduce it).
        Not a style filter -- just catches this specific failure so it is
        never silently reported as a successful deployment.
        """
        stripped = text.strip()
        if len(stripped) < 5:
            return True
        most_common_char_frac = max(stripped.count(c) for c in set(stripped)) / len(stripped)
        return most_common_char_frac > 0.6

    def _verify_ollama_deployment(self, model_name: str) -> bool:
        """Real post-deploy sanity generation. Returns False (not an
        exception) if the deployed Ollama model produces degenerate output --
        `deployed_to_ollama` must never be True for a model that doesn't
        actually work."""
        try:
            import requests
            resp = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": model_name,
                      "prompt": "Write a Python function that adds two numbers.",
                      "stream": False, "options": {"temperature": 0.0}},
                timeout=60,
            )
            text = resp.json().get("response", "")
            return not self._is_degenerate(text)
        except Exception:
            return False

    def _run_isolated_benchmark(self, before_model: str, after_model: str):
        """
        Real Pass@1 before/after via ModelBenchmarkEvaluator, with the
        orchestrator's persistent solution cache (saleha.core.memory_store)
        temporarily swapped for a throwaway store -- otherwise the second
        model's run just replays the first model's cached solution
        ("LLM skipped") instead of generating anything itself, which was
        verified to silently produce identical, meaningless before==after
        numbers. The real global memory store is always restored, never
        wiped.
        """
        import tempfile
        import saleha.core.memory_store as memory_store_mod
        from saleha.core.memory_store import MemoryStore
        import saleha.orchestrator as orch_mod
        from saleha.core.evaluator import ModelBenchmarkEvaluator

        real_store = memory_store_mod.memory_store
        throwaway = MemoryStore(storage_path=os.path.join(tempfile.mkdtemp(), "throwaway_memory.json"))
        memory_store_mod.memory_store = throwaway
        orch_mod.memory_store = throwaway
        try:
            ev = ModelBenchmarkEvaluator()
            throwaway.clear()
            before = ev.run_benchmark(model=before_model, limit=3)
            throwaway.clear()
            after = ev.run_benchmark(model=after_model, limit=3)
            return before.pass_rate, after.pass_rate
        finally:
            memory_store_mod.memory_store = real_store
            orch_mod.memory_store = real_store

    @staticmethod
    def _eval_loss(model, tokenizer, eval_ds, to_text_fn) -> float:
        """Real cross-entropy loss on held-out samples (lower = better)."""
        import torch
        model.eval()
        total_loss, n = 0.0, 0
        device = next(model.parameters()).device
        with torch.no_grad():
            for ex in eval_ds:
                text = to_text_fn(ex)
                enc = tokenizer(text, return_tensors="pt", truncation=True, max_length=1024).to(device)
                out = model(**enc, labels=enc["input_ids"])
                total_loss += float(out.loss)
                n += 1
        model.train()
        return total_loss / max(1, n)

    def register_with_ollama(self, model_name: str, adapter_path: str,
                              hf_base_model: Optional[str] = None) -> bool:
        """
        Merge the trained LoRA adapter into the base model and register the
        merged model with local Ollama.

        Real fix (2026-09-06, see _convert_to_gguf_via_llama_cpp): when a
        local llama.cpp checkout is available, its real
        convert_hf_to_gguf.py converts the merged model first and Ollama
        imports that .gguf directly -- verified end-to-end to produce
        correct, coherent output. Ollama's own built-in safetensors->GGUF
        conversion is used only as a fallback when llama.cpp isn't set up,
        since it was verified to silently produce degenerate output on
        this platform at every quantization level. Either way, nothing is
        ever reported as successfully deployed without a real post-deploy
        generation check (_verify_ollama_deployment).
        """
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            from peft import PeftModel

            base_id = hf_base_model or self._resolve_hf_base(TuningConfig().base_model)
            device = "cuda" if torch.cuda.is_available() else "cpu"
            base = AutoModelForCausalLM.from_pretrained(
                base_id, dtype=torch.bfloat16 if device == "cuda" else torch.float32, device_map=device,
            )
            merged = PeftModel.from_pretrained(base, adapter_path).merge_and_unload()

            merged_dir = os.path.join(self.work_dir, f"{model_name}_merged")
            os.makedirs(merged_dir, exist_ok=True)
            merged.save_pretrained(merged_dir, safe_serialization=True)
            tok = AutoTokenizer.from_pretrained(base_id)
            tok.save_pretrained(merged_dir)

            gguf_path = os.path.join(self.work_dir, f"{model_name}.gguf")
            real_gguf = _convert_to_gguf_via_llama_cpp(merged_dir, gguf_path)
            from_target = real_gguf or merged_dir

            modelfile_path = os.path.join(self.work_dir, f"{model_name}.Modelfile")
            with open(modelfile_path, "w", encoding="utf-8") as f:
                f.write(f"FROM {from_target}\nTEMPLATE {QWEN_CHATML_TEMPLATE}\nSYSTEM You are Saleha AI, a local expert coding assistant.\n")

            result = subprocess.run(
                ["ollama", "create", model_name, "-f", modelfile_path],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
            )
            if result.returncode != 0:
                return False
            # `ollama create` succeeding is not sufficient -- verified on this
            # platform that its GGUF conversion can silently produce a
            # degenerate model even on returncode 0. Never report deployed
            # without a real generation check confirming it actually works.
            return self._verify_ollama_deployment(model_name)
        except Exception:
            return False

    def merge_adapters_model_soup(self, adapter_paths: List[str], hf_base_model: str,
                                   output_name: str, weights: Optional[List[float]] = None,
                                   deploy_to_ollama: bool = True) -> "SoupMergeResult":
        """
        Real weight-space "model soup" merge: each adapter is merged into its
        own full copy of the base model (real merge_and_unload, same as
        register_with_ollama), then the resulting full weight tensors are
        averaged element-wise across all copies.

        This only works for adapters trained on the SAME base model -- LoRA
        rank/target_modules can differ freely (they don't need to match,
        since we average the full merged weights, not the raw LoRA A/B
        matrices), but the base architecture/dimensions must match.

        Weight averaging is a real, established technique ("model soup",
        Wortsman et al. 2022) -- this is not a fabricated shortcut, but it
        also is not guaranteed to help: it can produce a model that is worse
        than any single input if the adapters pull in conflicting directions.
        The returned result includes a real post-merge sanity generation so
        callers can see actual output, not just a success flag.
        """
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel

        if len(adapter_paths) < 2:
            return SoupMergeResult(success=False, output_name=output_name,
                                    error="Need >=2 adapter paths to merge.")
        w = weights or [1.0 / len(adapter_paths)] * len(adapter_paths)
        if len(w) != len(adapter_paths) or abs(sum(w) - 1.0) > 1e-6:
            return SoupMergeResult(success=False, output_name=output_name,
                                    error="weights must match adapter_paths length and sum to 1.0")

        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if device == "cuda" else torch.float32

        averaged_state: Dict[str, "torch.Tensor"] = {}
        try:
            for i, (path, wt) in enumerate(zip(adapter_paths, w)):
                base = AutoModelForCausalLM.from_pretrained(hf_base_model, dtype=dtype, device_map=device)
                merged = PeftModel.from_pretrained(base, path).merge_and_unload()
                sd = merged.state_dict()
                for key, tensor in sd.items():
                    contribution = tensor.detach().to(torch.float32) * wt
                    if key not in averaged_state:
                        averaged_state[key] = contribution.clone()
                    else:
                        averaged_state[key] += contribution
                del base, merged, sd
                if device == "cuda":
                    torch.cuda.empty_cache()

            final_model = AutoModelForCausalLM.from_pretrained(hf_base_model, dtype=dtype, device_map=device)
            cast_state = {k: v.to(final_model.state_dict()[k].dtype) for k, v in averaged_state.items()}
            final_model.load_state_dict(cast_state, strict=True)

            tokenizer = AutoTokenizer.from_pretrained(hf_base_model)
            sanity_prompt = "Write a Python function to check if a number is prime."
            enc = tokenizer(
                tokenizer.apply_chat_template([{"role": "user", "content": sanity_prompt}],
                                               add_generation_prompt=True, tokenize=False),
                return_tensors="pt",
            ).to(device)
            out = final_model.generate(**enc, max_new_tokens=60, do_sample=False)
            sanity_output = tokenizer.decode(out[0][enc.input_ids.shape[1]:], skip_special_tokens=True)

            merged_dir = os.path.join(self.work_dir, f"{output_name}_soup")
            os.makedirs(merged_dir, exist_ok=True)
            final_model.save_pretrained(merged_dir, safe_serialization=True)
            tokenizer.save_pretrained(merged_dir)

            deployed = False
            if deploy_to_ollama:
                modelfile_path = os.path.join(self.work_dir, f"{output_name}.Modelfile")
                with open(modelfile_path, "w", encoding="utf-8") as f:
                    f.write(f"FROM {merged_dir}\nTEMPLATE {QWEN_CHATML_TEMPLATE}\nSYSTEM You are Saleha AI, a local expert coding assistant.\n")
                result = subprocess.run(
                    ["ollama", "create", output_name, "-f", modelfile_path],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
                )
                deployed = result.returncode == 0 and self._verify_ollama_deployment(output_name)

            return SoupMergeResult(
                success=True, output_name=output_name, merged_path=merged_dir,
                num_adapters=len(adapter_paths), weights=w,
                sanity_output=sanity_output, deployed_to_ollama=deployed,
            )
        except Exception as e:
            return SoupMergeResult(success=False, output_name=output_name, error=str(e))


@dataclass
class SoupMergeResult:
    success: bool
    output_name: str
    merged_path: str = ""
    num_adapters: int = 0
    weights: Optional[List[float]] = None
    sanity_output: str = ""
    deployed_to_ollama: bool = False
    error: str = ""


# Global instance
lora_tuner = LoRATuner()
