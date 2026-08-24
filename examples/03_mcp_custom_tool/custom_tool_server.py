"""
Example Custom MCP Tool Server connected to Saleha AI via JSON-RPC 2.0
"""

import sys
import json

TOOLS = [
    {
        "name": "system_disk_usage",
        "description": "Returns current disk free space and capacity.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "default": "."}
            }
        }
    }
]

def handle_request(req):
    method = req.get("method")
    req_id = req.get("id")

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
    elif method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name")
        if tool_name == "system_disk_usage":
            import shutil
            total, used, free = shutil.disk_usage(".")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{
                        "type": "text",
                        "text": f"Total: {total // (1024**3)}GB, Free: {free // (1024**3)}GB"
                    }]
                }
            }
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}

if __name__ == "__main__":
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
        except Exception as e:
            sys.stderr.write(f"Error: {e}\n")

