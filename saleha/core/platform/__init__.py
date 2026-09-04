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

from saleha.core.smart_router import (
    SmartRouter,
    smart_router,
)
from saleha.core.model_provider import (
    ModelProvider,
    model_provider,
    default_provider,
    ProviderResponse,
    OllamaProvider,
    OpenAICompatibleProvider,
    MockProvider,
    FallbackChainProvider,
)
from saleha.core.git_native import (
    GitAutomationEngine,
    GitNativeManager,
    git_engine,
    git_native,
    GitCommitResult,
)
from saleha.core.lsp_engine import (
    LSPEngine,
    lsp_engine,
    LSPDiagnostic,
    DiagnosticReport,
)
from saleha.core.mcp_hub import (
    UniversalMCPHub,
    mcp_hub,
    MCPServerConfig,
)
from saleha.core.self_healer import (
    SelfHealingEngine,
    SelfHealer,
    self_healer,
)


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
