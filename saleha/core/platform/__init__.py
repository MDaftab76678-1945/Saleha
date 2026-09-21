"""
Saleha Core: Platform & Runtime Subsystem (2026 Frontier Standard)

Provides model routing, multi-provider inference backends, atomic Git automation,
Language Server Protocol (LSP) diagnostics, Model Context Protocol (MCP) hub,
and autonomous self-healing execution:
- SmartRouter / smart_router (Hardware-aware thermal & complexity model routing)
- ModelProvider / model_provider (Ollama, OpenAI-compatible, & Fallback providers)
- GitAutomationEngine / git_native (Conventional commits, worktrees, & safe atomic rollbacks)
- LSPEngine / lsp_engine (Polyglot compiler-grade type and syntax diagnostics)
- UniversalMCPHub / mcp_hub (Bidirectional MCP connectivity across IDEs)
- SelfHealingEngine / self_healer (Autonomous compiler & test failure auto-repair)
"""

from __future__ import annotations

from saleha.core.platform.git_native import (
    GitAutomationEngine,
    GitCommitResult,
    GitNativeManager,
    git_engine,
    git_native,
)
from saleha.core.platform.lsp_engine import (
    DiagnosticReport,
    LSPDiagnostic,
    LSPEngine,
    lsp_engine,
)
from saleha.core.platform.mcp_hub import (
    MCPServerConfig,
    UniversalMCPHub,
    mcp_hub,
)
from saleha.core.platform.model_provider import (
    FallbackChainProvider,
    MockProvider,
    ModelProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
    ProviderResponse,
    default_provider,
    model_provider,
)
from saleha.core.platform.self_healer import (
    SelfHealer,
    SelfHealingEngine,
)
from saleha.core.platform.smart_router import (
    SmartRouter,
    smart_router,
)


def __getattr__(name: str):
    # `self_healer` is a lazy singleton (see self_healer.py): constructing it
    # imports saleha.agents.base_agent, which imports
    # saleha.core.platform.model_provider -- importing it eagerly here, at
    # this package's own load time, would be a circular import.
    if name == "self_healer":
        from saleha.core.platform.self_healer import self_healer

        return self_healer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "SmartRouter",
    "smart_router",
    "ModelProvider",
    "model_provider",
    "default_provider",
    "ProviderResponse",
    "OllamaProvider",
    "OpenAICompatibleProvider",
    "MockProvider",
    "FallbackChainProvider",
    "GitAutomationEngine",
    "GitNativeManager",
    "git_engine",
    "git_native",
    "GitCommitResult",
    "LSPEngine",
    "lsp_engine",
    "LSPDiagnostic",
    "DiagnosticReport",
    "UniversalMCPHub",
    "mcp_hub",
    "MCPServerConfig",
    "SelfHealingEngine",
    "SelfHealer",
    "self_healer",
]
