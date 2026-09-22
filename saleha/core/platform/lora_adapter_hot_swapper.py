"""Saleha Core: Dynamic LoRA Adapter Hot-Swapper & Runtime Switcher.

Provides physical validation of adapter tensor files (GGUF / PyTorch Safetensors),
compiles dynamic Ollama Modelfiles, and manages zero-downtime runtime switching
across specialized micro-LoRA adapters in local memory.
"""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

CommandRunner = Callable[[List[str]], Tuple[int, str]]


def _run_command(cmd: List[str]) -> Tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600
        )
    except FileNotFoundError:
        return 127, f"{cmd[0]} not found on PATH"
    except subprocess.TimeoutExpired:
        return 124, f"{cmd[0]} timed out"
    return proc.returncode, (proc.stderr or proc.stdout).strip()


@dataclass
class AdapterMetadata:
    """Physical metadata extracted from a LoRA adapter file."""
    adapter_id: str
    file_path: str
    file_size_bytes: int
    format_type: str  # "GGUF", "SAFETENSORS", "PYTORCH_BIN"
    is_valid: bool
    base_model: str = "qwen2.5-coder:3b"
    rank_r: int = 16
    alpha: int = 32


@dataclass
class HotSwapResult:
    """Outcome of a dynamic adapter hot-swap operation."""
    success: bool
    previous_adapter_id: Optional[str]
    active_adapter_id: str
    modelfile_path: Optional[str]
    switch_latency_ms: float
    error_message: Optional[str] = None
    ollama_model: Optional[str] = None


class LoRAAdapterValidator:
    """Physical file format auditor verifying adapter integrity on disk."""

    GGUF_MAGIC = b"GGUF"

    @classmethod
    def validate_adapter_file(cls, path: Path | str) -> Tuple[bool, str, int]:
        """Inspects magic bytes and header structure of adapter file."""
        p = Path(path)
        if not p.exists() or not p.is_file():
            return False, "UNKNOWN", 0

        size = p.stat().st_size
        if size == 0:
            return False, "EMPTY_FILE", 0

        try:
            with open(p, "rb") as f:
                header = f.read(16)
                if header.startswith(cls.GGUF_MAGIC):
                    return True, "GGUF", size
                elif b"__metadata__" in header or b"safetensors" in header or p.suffix == ".safetensors":
                    return True, "SAFETENSORS", size
                elif p.suffix in [".bin", ".pt", ".pth"]:
                    return True, "PYTORCH_BIN", size
        except Exception:
            return False, "CORRUPTED", size

        return False, "UNKNOWN", size


class DynamicLoRAHotSwapper:
    """Manages active adapter state and compiles dynamic Modelfiles."""

    def __init__(
        self,
        base_model: str = "qwen2.5-coder:3b",
        registry_dir: Optional[Path] = None,
        runner: Optional[CommandRunner] = None,
    ) -> None:
        self.base_model = base_model
        self._run = runner or _run_command
        self.registry_dir = registry_dir or Path(".saleha/lora_registry")
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.active_adapter: Optional[AdapterMetadata] = None
        self.registered_adapters: Dict[str, AdapterMetadata] = {}

    def register_adapter(
        self,
        adapter_id: str,
        adapter_path: Path | str,
        base_model: Optional[str] = None,
        rank_r: int = 16,
        alpha: int = 32,
    ) -> AdapterMetadata:
        """Registers and validates an adapter file on disk."""
        path = Path(adapter_path).resolve()
        is_valid, fmt, size = LoRAAdapterValidator.validate_adapter_file(path)

        meta = AdapterMetadata(
            adapter_id=adapter_id,
            file_path=str(path),
            file_size_bytes=size,
            format_type=fmt,
            is_valid=is_valid,
            base_model=base_model or self.base_model,
            rank_r=rank_r,
            alpha=alpha,
        )
        self.registered_adapters[adapter_id] = meta
        return meta

    def compile_modelfile(self, meta: AdapterMetadata) -> Path:
        """Compiles a valid Ollama Modelfile linking the base model to the adapter."""
        modelfile_content = (
            f"FROM {meta.base_model}\n"
            f"ADAPTER {meta.file_path}\n"
            f"PARAMETER temperature 0.2\n"
            f"PARAMETER top_p 0.95\n"
            f"PARAMETER stop <|im_end|>\n"
        )
        out_path = self.registry_dir / f"Modelfile.{meta.adapter_id}"
        out_path.write_text(modelfile_content, encoding="utf-8")
        return out_path

    def hot_swap(self, adapter_id: str) -> HotSwapResult:
        """Executes zero-downtime switch to target adapter."""
        start_time = time.perf_counter()

        if adapter_id not in self.registered_adapters:
            return HotSwapResult(
                success=False,
                previous_adapter_id=self.active_adapter.adapter_id if self.active_adapter else None,
                active_adapter_id=self.active_adapter.adapter_id if self.active_adapter else "none",
                modelfile_path=None,
                switch_latency_ms=0.0,
                error_message=f"Adapter '{adapter_id}' is not registered.",
            )

        meta = self.registered_adapters[adapter_id]
        if not meta.is_valid:
            return HotSwapResult(
                success=False,
                previous_adapter_id=self.active_adapter.adapter_id if self.active_adapter else None,
                active_adapter_id=self.active_adapter.adapter_id if self.active_adapter else "none",
                modelfile_path=None,
                switch_latency_ms=0.0,
                error_message=f"Adapter file at '{meta.file_path}' failed physical integrity check.",
            )

        prev_id = self.active_adapter.adapter_id if self.active_adapter else None
        if meta.format_type not in ("GGUF", "SAFETENSORS"):
            return HotSwapResult(
                success=False,
                previous_adapter_id=prev_id,
                active_adapter_id=prev_id or "none",
                modelfile_path=None,
                switch_latency_ms=0.0,
                error_message=f"Ollama ADAPTER needs GGUF or safetensors, got {meta.format_type}.",
            )

        # The switch happens only if Ollama accepts the Modelfile.
        modelfile = self.compile_modelfile(meta)
        model_name = "saleha-" + re.sub(r"[^a-z0-9_.-]+", "-", adapter_id.lower())
        code, message = self._run(["ollama", "create", model_name, "-f", str(modelfile)])
        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 3)
        if code != 0:
            return HotSwapResult(
                success=False,
                previous_adapter_id=prev_id,
                active_adapter_id=prev_id or "none",
                modelfile_path=str(modelfile),
                switch_latency_ms=elapsed_ms,
                error_message=f"ollama create failed (exit {code}): {message}",
            )

        self.active_adapter = meta
        return HotSwapResult(
            success=True,
            previous_adapter_id=prev_id,
            active_adapter_id=adapter_id,
            modelfile_path=str(modelfile),
            switch_latency_ms=elapsed_ms,
            error_message=None,
            ollama_model=model_name,
        )
