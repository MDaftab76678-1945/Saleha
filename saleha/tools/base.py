"""Saleha Tools: Universal Tool Contract & Base Interface.

Provides standard BaseTool, ToolResult, and ToolRegistry for all developer,
agent, and autonomous self-synthesized tools in the Saleha ecosystem.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import inspect
import os
import importlib
import pathlib


@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
        }


class BaseTool(ABC):
    """Abstract base class for all Saleha executable tools."""

    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}

    def __init__(self):
        if not self.name:
            self.name = self.__class__.__name__

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Executes the tool with the provided arguments and returns ToolResult."""
        raise NotImplementedError

    def to_mcp_definition(self) -> Dict[str, Any]:
        """Converts tool to standard Model Context Protocol (MCP) tool schema."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.parameters or {
                "type": "object",
                "properties": {},
            },
            "handler": lambda params: self.execute(**params).to_dict(),
        }


class ToolRegistry:
    """Central registry and auto-discovery engine for Saleha tools."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Registers a tool instance into the registry."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        """Retrieves a registered tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[BaseTool]:
        """Returns a list of all registered tools."""
        return list(self._tools.values())

    def auto_discover(self, tools_dir: Optional[str] = None) -> int:
        """Discovers and registers all BaseTool subclasses in saleha/tools/."""
        if tools_dir is None:
            tools_dir = str(pathlib.Path(__file__).parent)

        count = 0
        for file in os.listdir(tools_dir):
            if file.endswith(".py") and not file.startswith("_") and file != "base.py":
                module_name = file[:-3]
                try:
                    mod = importlib.import_module(f"saleha.tools.{module_name}")
                    for attr_name in dir(mod):
                        attr = getattr(mod, attr_name)
                        if (
                            inspect.isclass(attr)
                            and issubclass(attr, BaseTool)
                            and attr is not BaseTool
                        ):
                            tool_inst = attr()
                            self.register(tool_inst)
                            count += 1
                except Exception:
                    continue
        return count


tool_registry = ToolRegistry()
