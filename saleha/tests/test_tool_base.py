"""Unit tests for saleha.tools.base, ToolRegistry, and ASTInspectorTool."""

from saleha.tools.base import BaseTool, ToolResult, ToolRegistry
from saleha.tools.ast_inspector import ASTInspectorTool


def test_tool_result() -> None:
    res_ok = ToolResult(success=True, data="data", metadata={"k": "v"})
    assert res_ok.success is True
    assert res_ok.data == "data"
    d = res_ok.to_dict()
    assert d["success"] is True
    assert d["data"] == "data"
    assert d["error"] is None
    assert d["metadata"] == {"k": "v"}

    res_err = ToolResult(success=False, error="Something went wrong")
    assert res_err.success is False
    assert res_err.error == "Something went wrong"


def test_ast_inspector_execution() -> None:
    tool = ASTInspectorTool()
    assert tool.name == "ast_inspector"
    assert "inspects python code" in tool.description.lower()

    sample_code = """
import os

class SampleClass:
    def method_one(self, x: int) -> int:
        if x > 0:
            return x * 2
        return 0
"""
    res = tool.execute(source_code=sample_code)
    assert res.success is True
    assert res.data["class_count"] == 1
    assert res.data["classes"][0]["name"] == "SampleClass"
    assert res.data["function_count"] == 1
    assert res.data["functions"][0]["name"] == "method_one"
    assert res.data["functions"][0]["cyclomatic_complexity"] >= 2
    assert res.data["import_count"] == 1

    # Error case: missing file
    err_res = tool.execute(file_path="non_existent_file_path_12345.py")
    assert err_res.success is False
    assert err_res.error is not None
    assert "File not found" in err_res.error


def test_ast_inspector_mcp_definition() -> None:
    tool = ASTInspectorTool()
    mcp_def = tool.to_mcp_definition()
    assert mcp_def["name"] == "ast_inspector"
    assert "properties" in mcp_def["inputSchema"]
    handler = mcp_def["handler"]
    assert callable(handler)

    sample_code = "def add(a: int, b: int) -> int:\n    return a + b\n"
    handler_out = handler({"source_code": sample_code})
    assert isinstance(handler_out, dict)
    assert handler_out["success"] is True
    assert handler_out["data"]["function_count"] == 1


def test_tool_registry() -> None:
    registry = ToolRegistry()
    assert len(registry.list_tools()) == 0

    tool = ASTInspectorTool()
    registry.register(tool)

    assert registry.get("ast_inspector") is tool
    assert registry.get("non_existent") is None
    assert len(registry.list_tools()) == 1


def test_nested_function_complexity_isolated() -> None:
    """Verifies that nested functions do not inflate the parent function's complexity."""
    tool = ASTInspectorTool()
    code = """
def outer(x: int) -> int:
    def inner(y: int) -> int:
        if y > 10:
            return y * 2
        elif y < 0:
            return -y
        return y
    return inner(x)
"""
    res = tool.execute(source_code=code)
    assert res.success is True
    funcs = {f["name"]: f for f in res.data["functions"]}

    # inner has base 1 + 2 ifs = 3
    assert funcs["inner"]["cyclomatic_complexity"] == 3
    # outer has base 1 + 0 ifs in its own scope = 1 (inner's decisions must NOT bleed into outer)
    assert funcs["outer"]["cyclomatic_complexity"] == 1


def test_ternary_and_comprehension_complexity() -> None:
    """Verifies that IfExp (ternary) and comprehensions are counted in cyclomatic complexity."""
    tool = ASTInspectorTool()
    code = """
def process_data(items: list) -> list:
    val = 10 if len(items) > 0 else 0
    filtered = [x for x in items if x > val]
    return filtered
"""
    res = tool.execute(source_code=code)
    assert res.success is True
    func = res.data["functions"][0]
    # base 1 + ternary(1) + comprehension(1 loop + 1 if) = 4
    assert func["cyclomatic_complexity"] >= 4


def test_full_argument_type_coverage() -> None:
    """Verifies that *args, **kwargs, and keyword-only args are validated for type coverage."""
    tool = ASTInspectorTool()
    # Function with untyped *args and **kwargs must NOT be marked fully typed
    untyped_varargs = """
def func_with_untyped_varargs(x: int, *args, **kwargs) -> int:
    return x
"""
    res1 = tool.execute(source_code=untyped_varargs)
    assert res1.success is True
    f1 = res1.data["functions"][0]
    assert f1["is_fully_typed"] is False
    assert f1["total_args_count"] == 3
    assert f1["typed_args_count"] == 1

    # Function where all arguments including *args and **kwargs are typed
    fully_typed_varargs = """
def func_fully_typed(x: int, *args: str, **kwargs: bool) -> int:
    return x
"""
    res2 = tool.execute(source_code=fully_typed_varargs)
    assert res2.success is True
    f2 = res2.data["functions"][0]
    assert f2["is_fully_typed"] is True
    assert f2["total_args_count"] == 3
    assert f2["typed_args_count"] == 3


def test_zero_functions_edge_case() -> None:
    """Verifies that a file with 0 functions returns 0.0% type coverage instead of 100.0%."""
    tool = ASTInspectorTool()
    code = """
CONSTANT_A = 100
CONSTANT_B = "hello"
"""
    res = tool.execute(source_code=code)
    assert res.success is True
    assert res.data["function_count"] == 0
    assert res.data["type_coverage_pct"] == 0.0


def test_security_findings_and_maintainability() -> None:
    """Verifies that security risks like eval and shell=True are detected and maintainability is scored."""
    tool = ASTInspectorTool()
    code = """
import subprocess

def run_payload(cmd: str) -> None:
    eval(cmd)
    subprocess.run(cmd, shell=True)
"""
    res = tool.execute(source_code=code)
    assert res.success is True
    assert res.data["security_findings_count"] >= 2
    rule_ids = [s["rule_id"] for s in res.data["security_findings"]]
    assert "SEC-001" in rule_ids  # eval
    assert "SEC-002" in rule_ids  # subprocess shell=True
    assert "maintainability_index" in res.data
    assert res.data["maintainability_grade"] in ("A", "B", "C")
