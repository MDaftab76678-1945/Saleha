"""
Process-level sandboxing pulled in from the v5 engine (see NOTEBOOK_IMPORT.md).

Platform note, because it is easy to get wrong: `sandbox_jail.HardenedSandbox`
is **POSIX only**. It applies rlimits between fork and exec, which Windows has
no equivalent for. Check `HardenedSandbox.is_available()` before using it, or
use `saleha.core.windows_job_sandbox` instead.

`ast_security_verifier.ASTContractAuditor` is pure AST work and runs anywhere.

This file exists so the directory is a real package. Without it these modules
were only importable with the directory itself on `sys.path`, which is why
`v5_production_core.py` carried flat `from local_llm_driver import ...`
imports that raised ModuleNotFoundError from anywhere else in the repo.
"""
