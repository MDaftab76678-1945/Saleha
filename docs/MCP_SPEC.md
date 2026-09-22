# Saleha AI — Model Context Protocol (MCP) Specification (not implemented)

> **Checked 2026-09-23:** none of the tool names below (`saleha_file_search`,
> `saleha_sast_scan`, `saleha_code_exec`, `saleha_git_commit`, `saleha_vault_get`)
> appear anywhere in `saleha/`, and there is no `saleha mcp` CLI command. This
> page is a design proposal, not documentation of running code. What exists is
> `saleha/core/platform/mcp_hub.py`.

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

