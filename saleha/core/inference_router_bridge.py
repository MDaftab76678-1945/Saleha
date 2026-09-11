"""
Saleha Rust Inference Router Bridge.

Thin Python wrapper around the `agent-inference-router` Rust crate
(rust/crates/agent-inference-router), built as a real PyO3 extension module via
`maturin` rather than embedded ad-hoc. This is a genuine cross-language call,
not a mock: the Rust side does the routing-tier decision (local model vs.
decentralized GPU network vs. premium cloud API) and this module simply loads
that compiled extension and calls into it.

Why PyO3/maturin instead of an HTTP/gRPC microservice:
- rust/crates/agent-inference-router/Cargo.toml already declares
  `pyo3 = { features = ["extension-module"] }` and `crate-type = ["cdylib", "rlib"]`
  -- i.e. it was already set up to be compiled as a Python extension, just never
  actually finished or wired up.
- The crate also contained a second, parallel `grpc_server.rs` (tonic/Axum-style
  gRPC service with its own `main()`), but that file does not compile: `tonic`
  is not even listed in Cargo.toml's dependencies, there is no `build.rs` to
  generate code from a `.proto` file, and no `.proto` file exists anywhere in
  the crate. It reads as an abandoned alternative sketch, not a working service.
- Given the crate's actual (working) dependency graph points at PyO3, and the
  routing logic here is pure, fast, synchronous decision logic (no I/O, no need
  for a network hop), an in-process extension module is the pragmatic choice
  for a local dev/demo project -- no extra process to keep alive, no port to
  manage.

What was actually broken and had to be fixed to make this real (see rust/crates/
agent-inference-router/Cargo.toml and src/lib.rs):
1. Cargo.toml declared `[features] python = ["pyo3"]` while `pyo3` was a
   mandatory (non-optional) dependency -- this is an invalid Cargo manifest and
   `cargo check`/`cargo build` fail outright with a manifest-parse error before
   any Rust code is even compiled. Removed the invalid feature declaration.
2. The crate was never added to the `rust/` Cargo workspace's `members`, and is
   still not (see rust/Cargo.toml) -- it is genuinely orphaned. A standalone
   `[workspace]` table was added to the crate's own Cargo.toml so it can be
   built independently of the (broken/aspirational) workspace.
3. `src/lib.rs` defined a `#[pyclass] InferenceRouter` with `#[pymethods]`, but
   had no `#[pymodule]` entry point at all -- so even a successful `cargo build`
   would never have produced anything Python could actually `import`. Added:

       #[pymodule]
       fn inference_router(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
           m.add_class::<InferenceRouter>()?;
           Ok(())
       }

After those three fixes, `maturin develop` (run from
rust/crates/agent-inference-router/) actually builds and installs the extension,
and `import inference_router; inference_router.InferenceRouter()` genuinely
works -- this was verified against an earlier Python/pyo3 combination, not assumed.

Re-checked 2026-09-11 against this project's current `.venv` (Python 3.14.7):
`cargo check --lib` in that crate directory now fails outright --
`pyo3 0.20.3`'s build script rejects Python 3.14 as newer than its supported
maximum (3.12). The crate itself did not regress; the interpreter it is
checked against did. Either pin pyo3 to a release that supports 3.14+, or set
`PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` and confirm the stable-ABI build
actually produces a loadable extension, before trusting this module's
"verified" claim again. Until then, treat is_available() == False on this
machine as the honest, current state -- not evidence the bridge itself is
broken.

Usage (once the extension is built -- see build_instructions() below):

    from saleha.core.inference_router_bridge import rust_inference_router

    if rust_inference_router.is_available():
        decision = rust_inference_router.route(
            task_id="t1", prompt="...", complexity_score=0.85,
            privacy_required=False, max_budget_usd=0.10,
        )
        # decision == {"target": "GPT-4-Turbo", "node_id": "openai",
        #              "estimated_latency_ms": 1500.0, "estimated_cost_usd": 0.05}

This is intentionally a standalone utility -- it does not force itself into
saleha/core/smart_router.py or saleha/core/model_provider.py's existing
(working) Ollama-based routing. Either module could optionally consult
`rust_inference_router.route(...)` as an extra signal (e.g. to decide the
Local-vs-Decentralized-vs-Premium *tier* before smart_router picks a concrete
installed Ollama model within that tier), but that integration is left to a
follow-up since it changes existing routing behavior.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

try:
    import inference_router as _rust_ext

    _EXT_AVAILABLE = True
    _EXT_IMPORT_ERROR: Optional[str] = None
except ImportError as exc:
    _rust_ext = None  # type: ignore
    _EXT_AVAILABLE = False
    _EXT_IMPORT_ERROR = str(exc)


class RustInferenceRouterUnavailable(RuntimeError):
    """Raised when the compiled `inference_router` PyO3 extension isn't installed."""


def build_instructions() -> str:
    return (
        "The 'inference_router' Rust extension is not built/installed.\n"
        "From the repo root:\n"
        "  pip install maturin\n"
        "  cd rust/crates/agent-inference-router\n"
        "  maturin develop\n"
        "This compiles the PyO3 extension module and installs it (editable) into "
        "the active Python environment."
    )


class RustInferenceRouterBridge:
    """Wraps the compiled `inference_router.InferenceRouter` PyO3 class."""

    def __init__(self):
        self._router = _rust_ext.InferenceRouter() if _EXT_AVAILABLE else None

    def is_available(self) -> bool:
        return _EXT_AVAILABLE

    def import_error(self) -> Optional[str]:
        return _EXT_IMPORT_ERROR

    def register_node(
        self,
        peer_id: str,
        current_load: float,
        avg_latency_ms: float,
        cost_per_token: float,
        supports_fhe: bool,
    ) -> None:
        if not _EXT_AVAILABLE:
            raise RustInferenceRouterUnavailable(build_instructions())
        self._router.register_node(
            peer_id, current_load, avg_latency_ms, cost_per_token, supports_fhe
        )

    def get_node_count(self) -> int:
        if not _EXT_AVAILABLE:
            raise RustInferenceRouterUnavailable(build_instructions())
        return self._router.get_node_count()

    def route(
        self,
        task_id: str,
        prompt: str,
        complexity_score: float,
        privacy_required: bool,
        max_budget_usd: float,
    ) -> Dict[str, Any]:
        """Real call across the Python/Rust boundary -- not a mock/stub.

        Raises RustInferenceRouterUnavailable (with build instructions) instead
        of silently returning a fabricated routing decision when the extension
        isn't built.
        """
        if not _EXT_AVAILABLE:
            raise RustInferenceRouterUnavailable(build_instructions())
        return self._router.route_request(
            {
                "task_id": task_id,
                "prompt": prompt,
                "complexity_score": complexity_score,
                "privacy_required": privacy_required,
                "max_budget_usd": max_budget_usd,
            }
        )


rust_inference_router = RustInferenceRouterBridge()
