"""
Saleha Core: Structured Cognitive Reasoning & XML Tool Calling Engine

Provides sovereign structured reasoning tokens and open XML tool calling:
1. Structured Scratchpad & Thinking Token Extraction:
   - <THINKING>...</THINKING>
   - <SCRATCHPAD>...</SCRATCHPAD>
   - <PLAN>...</PLAN>
2. Backend-Agnostic XML Tool Calling:
   - <tools> schema injection
   - <tool_call> parsing (JSON payload or XML tag structure)
   - <tool_response> formatting for multi-turn conversational loops
3. Evidence Grounding & Code Citations:
   - <co file="..." line="...">...</co>
"""

from __future__ import annotations

import re
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple


@dataclass
class StructuredToolCall:
    name: str
    arguments: Dict[str, Any]
    raw_block: str = ""


@dataclass
class GroundedCitation:
    file_path: str
    line_number: Optional[int]
    content: str


@dataclass
class ParsedCognitiveTurn:
    thinking: str = ""
    plan: str = ""
    tool_calls: List[StructuredToolCall] = field(default_factory=list)
    citations: List[GroundedCitation] = field(default_factory=list)
    clean_response: str = ""


class StructuredReasoner:
    """Parser and prompt formatter for Saleha sovereign structured reasoning and tool calling."""

    THINKING_PATTERN = re.compile(r"<(?:THINKING|thinking)>(.*?)</(?:THINKING|thinking)>", re.DOTALL | re.IGNORECASE)
    SCRATCHPAD_PATTERN = re.compile(r"<(?:SCRATCHPAD|scratchpad)>(.*?)</(?:SCRATCHPAD|scratchpad)>", re.DOTALL | re.IGNORECASE)
    PLAN_PATTERN = re.compile(r"<(?:PLAN|plan)>(.*?)</(?:PLAN|plan)>", re.DOTALL | re.IGNORECASE)
    TOOL_CALL_PATTERN = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL | re.IGNORECASE)
    CITATION_PATTERN = re.compile(r'<co\s+file="([^"]+)"(?:\s+line="?(\d+)"?)?>(.*?)</co>', re.DOTALL | re.IGNORECASE)

    # A reasoning block whose closing tag never arrived. Reasoning models
    # (qwen3, deepseek-r1) open <think> and can stop mid-thought when they hit
    # a token budget or a timeout, so the closer is simply absent. The paired
    # patterns above match nothing in that case and the entire raw trace --
    # often thousands of tokens -- flows on as if it were the answer.
    #
    # Measured on this repo's own benchmark: a truncated reply left the tag in
    # the extracted code and the task failed with a SyntaxError, which was
    # recorded as a model failure. It was not; the harness had kept text that
    # was never meant to be code.
    UNCLOSED_REASONING_PATTERN = re.compile(
        r"<(?:THINKING|thinking|think|SCRATCHPAD|scratchpad)>(?![\s\S]*?"
        r"</(?:THINKING|thinking|think|SCRATCHPAD|scratchpad)>)[\s\S]*$",
        re.IGNORECASE,
    )

    @classmethod
    def strip_reasoning(cls, text: str) -> str:
        """
        Remove reasoning blocks, closed or not.

        Callers that only ran the closed-tag patterns kept truncated traces:
        `<think>partial reasoning` with no closer survived intact. This is the
        single place that handles both, so a fix here reaches every caller.
        """
        if not text:
            return ""
        cleaned = cls.THINKING_PATTERN.sub("", text)
        cleaned = cls.SCRATCHPAD_PATTERN.sub("", cleaned)
        cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = cls.UNCLOSED_REASONING_PATTERN.sub("", cleaned)
        return re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    @classmethod
    def extract_reasoning(cls, text: str) -> str:
        """The reasoning text itself, from a closed block or a truncated one."""
        if not text:
            return ""
        match = (cls.THINKING_PATTERN.search(text)
                 or cls.SCRATCHPAD_PATTERN.search(text)
                 or re.search(r"<think>(.*?)</think>", text, re.DOTALL | re.IGNORECASE))
        if match:
            return match.group(1).strip()
        truncated = cls.UNCLOSED_REASONING_PATTERN.search(text)
        if truncated:
            return re.sub(r"^<[^>]+>", "", truncated.group(0)).strip()
        return ""

    @classmethod
    def format_system_prompt_with_tools(cls, base_prompt: str, tools: List[Dict[str, Any]]) -> str:
        """Injects <tools> XML definitions and structured reasoning token constraints."""
        tools_xml_parts = ["<tools>"]
        for t in tools:
            tools_xml_parts.append(json.dumps(t, indent=2))
        tools_xml_parts.append("</tools>")

        instructions = (
            "You are an autonomous polyglot software engineering intelligence.\n"
            "When performing complex reasoning or refactoring, ALWAYS structure your internal deliberation inside:\n"
            "<THINKING>\n"
            "1. Architectural & AST invariants\n"
            "2. Causal root-cause hypothesis\n"
            "3. Step-by-step verification plan\n"
            "</THINKING>\n\n"
            "To invoke a tool, emit a <tool_call> block formatted as:\n"
            "<tool_call>\n"
            '{"name": "tool_name", "arguments": {"arg1": "val1"}}\n'
            "</tool_call>\n"
        )
        return f"{base_prompt}\n\n{instructions}\n\n" + "\n".join(tools_xml_parts)

    @classmethod
    def parse_turn(cls, text: str) -> ParsedCognitiveTurn:
        """Parses reasoning scratchpad, tool calls, and citations from generated text."""
        result = ParsedCognitiveTurn()
        clean = text or ""

        # 1. Extract Thinking (closed blocks and truncated ones alike)
        result.thinking = cls.extract_reasoning(clean)
        if result.thinking:
            clean = cls.strip_reasoning(clean)

        # 2. Extract Plan
        p_match = cls.PLAN_PATTERN.search(clean)
        if p_match:
            result.plan = p_match.group(1).strip()
            clean = cls.PLAN_PATTERN.sub("", clean).strip()

        # 3. Extract Tool Calls
        for tc_match in cls.TOOL_CALL_PATTERN.finditer(clean):
            raw_content = tc_match.group(1).strip()
            parsed_call = cls._parse_single_tool_call(raw_content)
            if parsed_call:
                parsed_call.raw_block = tc_match.group(0)
                result.tool_calls.append(parsed_call)

        # 4. Extract Citations
        for c_match in cls.CITATION_PATTERN.finditer(clean):
            fpath = c_match.group(1)
            lineno = int(c_match.group(2)) if c_match.group(2) else None
            c_content = c_match.group(3).strip()
            result.citations.append(GroundedCitation(file_path=fpath, line_number=lineno, content=c_content))

        result.clean_response = clean.strip()
        return result

    @classmethod
    def _parse_single_tool_call(cls, content: str) -> Optional[StructuredToolCall]:
        # Style A: JSON format inside <tool_call>
        try:
            data = json.loads(content)
            name = data.get("name") or data.get("tool")
            args = data.get("arguments") or data.get("args") or {}
            if name and isinstance(args, dict):
                return StructuredToolCall(name=str(name), arguments=args)
        except json.JSONDecodeError:
            pass

        # Style B: XML tag format (<name>...</name><arguments>...</arguments>)
        name_m = re.search(r"<name>\s*(\w+)\s*</name>", content)
        args_m = re.search(r"<arguments>\s*(\{.*?\})\s*</arguments>", content, re.DOTALL)
        if name_m:
            name = name_m.group(1).strip()
            args = {}
            if args_m:
                try:
                    args = json.loads(args_m.group(1))
                except json.JSONDecodeError:
                    args = {}
            return StructuredToolCall(name=name, arguments=args)

        return None

    @classmethod
    def format_tool_response(cls, tool_name: str, content: Any) -> str:
        """Formats an execution observation into an XML <tool_response> block."""
        data = {
            "name": tool_name,
            "content": content
        }
        return f"<tool_response>\n{json.dumps(data, ensure_ascii=False, indent=2)}\n</tool_response>"


structured_reasoner = StructuredReasoner()
ParsedTurn = ParsedCognitiveTurn
