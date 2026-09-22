# Saleha AI — Model Context Protocol (MCP) Specification

> **Checked against the code 2026-09-23.** `saleha mcp serve` starts the stdio
> JSON-RPC server (`saleha/core/mcp_engine.py`); `saleha mcp list/export/connect`
> manage external servers (`saleha/core/platform/mcp_hub.py`). The tools the
> server really exposes are the `name=` entries in `mcp_engine.py`
> (`saleha_team_swarm`, `saleha_dag_execute`, `saleha_sast_scan`,
> `saleha_sandbox_run`, `saleha_memory_recall`). The table and the `--stdio` /
> `--port` examples below are an older proposal and do not match: only
> `saleha_sast_scan` exists, and there is no `--port` HTTP mode.

Saleha implements the universal **Model Context Protocol (JSON-RPC 2.0)** to seamlessly connect internal agents to external developer tooling and expose Saleha capabilities to external IDEs and agents.

---

## 1. Dual Architecture

1. **MCP Server**: Runs over `stdio` or `HTTP/SSE` and exposes Saleha core capabilities (file search, AST security scanning, polyglot execution, git commit) as standard tools.
2. **MCP Client**: Allows Saleha agents to dynamically call external MCP servers (databases, browser agents, GitHub integrations).

---

## 2. Built-in Core MCP Tools

| Tool Name | Parameters | Description |
|---|---|---|
| `saleha_file_search` | `pattern: str, dir_path: str` | Fast recursive glob search across codebase. |
| `saleha_sast_scan` | `path: str, severity: str` | AST-based static security vulnerability analysis. |
| `saleha_code_exec` | `code: str, language: str` | Sandboxed execution of code with safety guardrails. |
| `saleha_git_commit` | `message: str, files: list` | Atomic conventional commit creation. |
| `saleha_vault_get` | `key: str` | Secure retrieval of encrypted vault credentials. |

---

## 3. Running MCP Server

### Stdio Mode (for VS Code & Cursor):
```powershell
saleha mcp --stdio
```

### HTTP / SSE Mode (for Web Clients):
```powershell
saleha mcp --port 8080
```

