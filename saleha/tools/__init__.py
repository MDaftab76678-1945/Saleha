"""Saleha Tools Package.

Exports BaseTool, ToolResult, and tool_registry for all developer and agent tools.
"""

from saleha.tools.base import BaseTool, ToolResult, ToolRegistry, tool_registry
from saleha.tools.ast_inspector import ASTInspectorTool
from saleha.tools.git_status_auditor import GitStatusAuditorTool

# Register built-in tools
tool_registry.register(ASTInspectorTool())
tool_registry.register(GitStatusAuditorTool())

__all__ = [
    "BaseTool",
    "ToolResult",
    "ToolRegistry",
    "tool_registry",
    "ASTInspectorTool",
    "GitStatusAuditorTool",
]
