"""
J.A.R.V.I.S. Central Configuration
===================================
37-Subsystem Production Architecture - Master Config
Air-Gapped | Bare-Metal | Sub-15ms SLA
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# =============================================================================
# PATHS
# =============================================================================
JARVIS_ROOT = Path(__file__).parent.parent.resolve()
MODELS_DIR = JARVIS_ROOT / "models"
VAULT_DIR = JARVIS_ROOT / "vault"
DATA_DIR = JARVIS_ROOT / "data"
LOGS_DIR = DATA_DIR / "logs"
SKILLS_DIR = JARVIS_ROOT / "skills" / "custom"

# Ensure directories exist
for _dir in [MODELS_DIR, VAULT_DIR, DATA_DIR, LOGS_DIR, SKILLS_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)


# =============================================================================
# SLA BUDGET (End-to-End Latency Targets)
# =============================================================================
@dataclass(frozen=True)
class SLABudget:
    """Production SLA Thresholds (milliseconds)"""
    NETWORK_INGEST: float = 0.10       # eBPF AF_XDP
    VAD_AEC: float = 0.10              # ESP32 Differential Filter
    FEATURE_EXTRACTION: float = 0.20   # Fused CUDA Mel Kernel
    STT_TRANSCRIPTION: float = 5.00    # TensorRT Whisper
    SPECULATIVE_LLM: float = 0.50      # PagedAttention KV-Cache
    TTS_SYNTHESIS: float = 4.00        # Kokoro-82M ONNX
    UDP_PUSH: float = 2.00             # WebRTC DataChannel
    TOTAL_E2E: float = 15.00           # Master Budget


SLA = SLABudget()


# =============================================================================
# AUDIO CONFIGURATION
# =============================================================================
@dataclass(frozen=True)
class AudioConfig:
    SAMPLE_RATE: int = 16000
    CHUNK_SIZE: int = 1024
    FRAME_DURATION_MS: int = 30
    ENERGY_THRESHOLD: int = 1400
    SILENCE_TIMEOUT_MS: int = 800
    VAD_MODEL: str = "silero_vad"
    STT_MODEL: str = "base.en"
    STT_DEVICE: str = "cpu"
    STT_COMPUTE_TYPE: str = "int8"


AUDIO = AudioConfig()


# =============================================================================
# LLM CONFIGURATION
# =============================================================================
@dataclass(frozen=True)
class LLMConfig:
    OLLAMA_HOST: str = "http://localhost:11434"
    PRIMARY_MODEL: str = "qwen2.5:7b"
    VISION_MODEL: str = "qwen2.5vl:7b"
    DRAFT_MODEL: str = "qwen2.5:0.5b"  # Speculative Decoding
    EMBEDDING_MODEL: str = "nomic-embed-text"
    TEMPERATURE: float = 0.2
    MAX_TOKENS: int = 512
    STREAM: bool = True


LLM = LLMConfig()


# =============================================================================
# TTS CONFIGURATION
# =============================================================================
@dataclass(frozen=True)
class TTSConfig:
    KOKORO_MODEL: str = str(MODELS_DIR / "kokoro-v0_19.onnx")
    VOICES_JSON: str = str(MODELS_DIR / "voices.json")
    VOICE_NAME: str = "af_sarah"
    SAMPLE_RATE: int = 24000
    SPEED: float = 1.1
    LANGUAGE: str = "en-us"


TTS = TTSConfig()


# =============================================================================
# MEMORY CONFIGURATION
# =============================================================================
@dataclass(frozen=True)
class MemoryConfig:
    DUCKDB_PATH: str = str(DATA_DIR / "episodic.duckdb")
    KUZU_PATH: str = str(DATA_DIR / "kuzu_graph")
    RRF_K_CONSTANT: int = 60
    VECTOR_DIM: int = 384
    TOP_K: int = 5


MEMORY = MemoryConfig()


# =============================================================================
# IPC CONFIGURATION
# =============================================================================
@dataclass(frozen=True)
class IPCConfig:
    ZMQ_HOST: str = "tcp://127.0.0.1"
    ZMQ_PORT: int = 5555
    ZMQ_ENDPOINT: str = f"{ZMQ_HOST}:{ZMQ_PORT}"
    WEB_GATEWAY_PORT: int = 8765


IPC = IPCConfig()


# =============================================================================
# SECURITY CONFIGURATION
# =============================================================================
@dataclass(frozen=True)
class SecurityConfig:
    VAULT_PATH: str = str(VAULT_DIR / "secrets.enc")
    ENCRYPTION: str = "AES-256-GCM"
    MAX_COMMAND_TIMEOUT: int = 15
    BANNED_PATTERNS: List[str] = field(default_factory=lambda: [
        r"rm\s+-rf", r"sudo", r"mkfs", r"dd\s+if=", r"shutdown", r"reboot"
    ])


SECURITY = SecurityConfig()


# =============================================================================
# SUBSYSTEM REGISTRY (37 Modules)
# =============================================================================
SUBSYSTEMS: Dict[str, Dict] = {
    "audio_duplex": {"module": "core.audio.duplex", "status": "OFFLINE"},
    "tts_kokoro": {"module": "engine.tts.kokoro", "status": "OFFLINE"},
    "memory_hybrid": {"module": "core.memory.hybrid", "status": "OFFLINE"},
    "orchestrator": {"module": "engine.orchestrator.dag", "status": "OFFLINE"},
    "vision_ambient": {"module": "core.vision.ambient", "status": "OFFLINE"},
    "security_sandbox": {"module": "core.security.sandbox", "status": "OFFLINE"},
    "ipc_zmq": {"module": "core.network.zmq_bus", "status": "OFFLINE"},
    "self_debugger": {"module": "engine.agents.debugger", "status": "OFFLINE"},
    "pty_terminal": {"module": "core.hardware.pty", "status": "OFFLINE"},
    "memory_consolidator": {"module": "core.memory.consolidator", "status": "OFFLINE"},
    "gui_automator": {"module": "core.vision.gui", "status": "OFFLINE"},
    "secret_vault": {"module": "core.security.vault", "status": "OFFLINE"},
    "web_agent": {"module": "engine.agents.web", "status": "OFFLINE"},
    "smart_home": {"module": "bridge.smart_home.mqtt", "status": "OFFLINE"},
    "spatial_vision": {"module": "core.vision.spatial", "status": "OFFLINE"},
    "watchdog": {"module": "core.hardware.watchdog", "status": "OFFLINE"},
}


# =============================================================================
# VALIDATION
# =============================================================================
def validate_environment() -> Dict[str, bool]:
    """Verify all critical dependencies before boot"""
    checks = {}

    # GPU Check
    try:
        import pynvml
        pynvml.nvmlInit()
        checks["gpu"] = True
        pynvml.nvmlShutdown()
    except Exception:
        checks["gpu"] = False

    # Ollama Check
    try:
        import requests
        r = requests.get(f"{LLM.OLLAMA_HOST}/api/tags", timeout=2)
        checks["ollama"] = r.status_code == 200
    except Exception:
        checks["ollama"] = False

    # Audio Check
    try:
        import pyaudio
        pa = pyaudio.PyAudio()
        checks["audio"] = pa.get_device_count() > 0
        pa.terminate()
    except Exception:
        checks["audio"] = False

    return checks


if __name__ == "__main__":
    print("=" * 60)
    print("  J.A.R.V.I.S. CONFIGURATION VALIDATOR")
    print("=" * 60)
    results = validate_environment()
    for key, status in results.items():
        icon = "✅" if status else "❌"
        print(f"  {icon} {key.upper():15} : {'ONLINE' if status else 'OFFLINE'}")
    print("=" * 60)
