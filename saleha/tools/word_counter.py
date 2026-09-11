from typing import Any

from saleha.tools.base import BaseTool, ToolResult


class WordCounterTool(BaseTool):
    name = "word_counter"
    description = "Counts the number of words in a given text"
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to count words from"}
        },
        "required": ["text"],
    }

    def execute(self, **kwargs: Any) -> ToolResult:
        text = kwargs.get("text", "")
        word_count = len(text.split())
        return ToolResult(success=True, data={"word_count": word_count})