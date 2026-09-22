"""Tests for Saleha's 4 Ultimate Technical Frontiers.

1. Headless Browser Auto-Spinup & Route Renderer
2. CPG & AST Context Window Slicer for Local 3B/8B Models
3. Dynamic LoRA Adapter Hot-Swapper & Runtime Switcher
4. Semantic 3-Way Git Merge Conflict Arbiter
"""

import shutil
import tempfile
from pathlib import Path

import pytest

from saleha.core.cognitive.cpg_context_slicer import CPGContextSlicer
from saleha.core.git.semantic_merge_arbiter import SemanticMergeArbiter
from saleha.core.platform.lora_adapter_hot_swapper import (
    DynamicLoRAHotSwapper,
    LoRAAdapterValidator,
)
from saleha.core.vision.headless_browser_renderer import HeadlessBrowserRenderer


@pytest.fixture(autouse=True)
def test_mode_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SALEHA_TEST_MODE", "1")
    monkeypatch.setenv("PYTHONIOENCODING", "utf-8")


# ---------------------------------------------------------------------------
# 1. Headless Browser Route Renderer Tests
# ---------------------------------------------------------------------------

def test_headless_browser_renderer_extraction() -> None:
    renderer = HeadlessBrowserRenderer(default_width=1280.0, default_height=800.0)

    html = """
    <html>
        <body>
            <header id="main-nav" style="width: 1280px; height: 60px; background-color: #000000; color: #ffffff;">
                Navigation Title
            </header>
            <main>
                <div class="card" style="width: 300px; height: 150px; background-color: #ffffff; color: #333333; font-size: 14px;">
                    Card Content
                </div>
            </main>
        </body>
    </html>
    """

    elements = renderer.render_html_to_elements(html)
    assert len(elements) >= 2

    header_elem = next(e for e in elements if e.selector == "#main-nav")
    assert header_elem.bbox.width == 1280.0
    assert header_elem.bbox.height == 60.0
    assert header_elem.text_color == "#ffffff"
    assert header_elem.background_color == "#000000"


def test_headless_browser_renderer_visual_audit_pipeline() -> None:
    renderer = HeadlessBrowserRenderer(default_width=320.0, default_height=568.0)

    # HTML with low contrast and layout bleeding
    html = """
    <div style="position: absolute; left: 10px; top: 10px; width: 400px; height: 80px; background-color: #ffffff; color: #cccccc;">
        Faint wide text spilling out of mobile screen
    </div>
    """

    report = renderer.audit_html_string(html, viewport_name="mobile_compact", width=320.0, height=568.0)
    assert report.is_clean is False
    assert len(report.clipping_defects) == 1
    assert report.clipping_defects[0].overflow_x >= 80.0  # (10 + 400) - 320 = 90.0
    assert len(report.contrast_defects) == 1


# ---------------------------------------------------------------------------
# 2. CPG & AST Context Window Slicer Tests
# ---------------------------------------------------------------------------

def test_cpg_context_slicer_dependency_slice() -> None:
    slicer = CPGContextSlicer()

    monolithic_code = """
import math
import os
from typing import List

GLOBAL_SALT = 42
UNRELATED_GLOBAL = "ignore_me"

def helper_math(a: int) -> int:
    return a * GLOBAL_SALT

def unrelated_huge_algorithm():
    # 50 lines of unrelated complex logic
    x = 100
    for i in range(100):
        x += i
    return x

def target_function(val: int) -> int:
    # Target function that references helper_math and GLOBAL_SALT
    return helper_math(val) + 10

def another_unrelated_function():
    return "unrelated"
"""

    result = slicer.slice_file(
        source_code=monolithic_code,
        target_symbol="target_function",
    )

    assert result.original_line_count > 15
    assert result.sliced_line_count < result.original_line_count
    assert result.compression_ratio > 0.0

    # Ensure target function, referenced helper, and needed global are retained
    assert "def target_function" in result.sliced_code
    assert "def helper_math" in result.sliced_code
    assert "GLOBAL_SALT = 42" in result.sliced_code

    # Ensure completely unrelated functions and variables are sliced out
    assert "unrelated_huge_algorithm" not in result.sliced_code
    assert "another_unrelated_function" not in result.sliced_code
    assert "UNRELATED_GLOBAL" not in result.sliced_code


def test_cpg_context_slicer_sliding_fallback() -> None:
    slicer = CPGContextSlicer()
    unparseable_code = "syntax error line 1 (\nsyntax error line 2\n" * 20

    result = slicer.slice_file(
        source_code=unparseable_code,
        target_line=10,
    )
    assert result.sliced_code != ""
    assert result.sliced_line_count <= 50


# ---------------------------------------------------------------------------
# 3. Dynamic LoRA Adapter Hot-Swapper Tests
# ---------------------------------------------------------------------------

def test_lora_adapter_hot_swapper() -> None:
    temp_dir = Path(tempfile.mkdtemp())
    try:
        # Create a mock GGUF adapter file
        gguf_file = temp_dir / "qwen_coder_micro.gguf"
        with open(gguf_file, "wb") as f:
            f.write(b"GGUF\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00")

        # Validate file
        is_valid, fmt, size = LoRAAdapterValidator.validate_adapter_file(gguf_file)
        assert is_valid is True
        assert fmt == "GGUF"
        assert size == 16

        # Register and hot-swap
        registry = temp_dir / "registry"
        swapper = DynamicLoRAHotSwapper(base_model="qwen2.5-coder:3b", registry_dir=registry)

        meta = swapper.register_adapter(
            adapter_id="coder_v1",
            adapter_path=gguf_file,
            rank_r=16,
            alpha=32,
        )
        assert meta.is_valid is True

        swap_res = swapper.hot_swap("coder_v1")
        assert swap_res.success is True
        assert swap_res.active_adapter_id == "coder_v1"
        assert swap_res.switch_latency_ms >= 0.0
        assert swap_res.modelfile_path is not None
        assert Path(swap_res.modelfile_path).exists()
        assert f"ADAPTER {gguf_file.resolve()}" in Path(swap_res.modelfile_path).read_text(encoding="utf-8")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# 4. Semantic 3-Way Git Merge Conflict Arbiter Tests
# ---------------------------------------------------------------------------

def test_semantic_merge_arbiter_adjacent_symbols() -> None:
    arbiter = SemanticMergeArbiter()

    conflicted_source = """
import math

<<<<<<< HEAD
def calculate_discount(price: float) -> float:
    return price * 0.9
=======
def calculate_tax(price: float) -> float:
    return price * 1.15
>>>>>>> incoming

def format_currency(amount: float) -> str:
    return f"${amount:.2f}"
"""

    result = arbiter.resolve_conflicted_content(conflicted_source, "billing.py")
    assert result.status == "CLEAN_RESOLVED"
    assert result.total_conflicts == 1
    assert result.resolved_conflicts == 1
    assert result.is_valid_ast is True

    # Both non-conflicting functions should be cleanly united
    assert "def calculate_discount" in result.resolved_code
    assert "def calculate_tax" in result.resolved_code
    assert "def format_currency" in result.resolved_code
    assert "<<<<<<<" not in result.resolved_code


def test_semantic_merge_arbiter_unresolvable_conflict() -> None:
    arbiter = SemanticMergeArbiter()

    # Direct contradictory modification of the exact same function body
    conflicted_source = """
<<<<<<< HEAD
def get_status():
    return "ACTIVE"
=======
def get_status():
    return "TERMINATED"
>>>>>>> incoming
"""

    result = arbiter.resolve_conflicted_content(conflicted_source, "status.py")
    assert result.status == "MANUAL_REQUIRED"
    assert result.unresolved_conflicts == 1
