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

from saleha.core.git_native import (
    GitAutomationEngine,
    GitCommitResult,
    GitNativeManager,
    git_engine,
    git_native,
)
from saleha.core.lsp_engine import (
    DiagnosticReport,
    LSPDiagnostic,
    LSPEngine,
    lsp_engine,
)
from saleha.core.mcp_hub import (
    MCPServerConfig,
    UniversalMCPHub,
    mcp_hub,
)
from saleha.core.model_provider import (
    FallbackChainProvider,
    MockProvider,
    ModelProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
    ProviderResponse,
    default_provider,
    model_provider,
)
from saleha.core.self_healer import (
    SelfHealer,
    SelfHealingEngine,
    self_healer,
)
from saleha.core.smart_router import (
    SmartRouter,
    smart_router,
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
