import json
import sys
from typing import Any

from src.skills.base import SKILL_REGISTRY
from src.skills.catalog import load_builtin_skills


def _send_response(response_id: str, result: Any):
    msg = {
        "jsonrpc": "2.0",
        "id": response_id,
        "result": result,
    }
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def _send_error(response_id: str, code: int, message: str):
    msg = {
        "jsonrpc": "2.0",
        "id": response_id,
        "error": {"code": code, "message": message},
    }
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def serve_mcp():
    load_builtin_skills()
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params", {})

            if method == "initialize":
                _send_response(
                    req_id,
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "UniversalAgentHarness", "version": "1.0.0"},
                    },
                )
            elif method == "tools/list":
                tools = []
                for name, skill in SKILL_REGISTRY.items():
                    tools.append(
                        {
                            "name": name,
                            "description": skill.description or "Skill tool",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "args": {"type": "string", "description": "Arguments as JSON string"}
                                },
                            },
                        }
                    )
                _send_response(req_id, {"tools": tools})
            elif method == "tools/call":
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})

                if tool_name in SKILL_REGISTRY:
                    try:
                        args_to_pass = tool_args
                        if "args" in tool_args:
                            args_to_pass = json.loads(tool_args["args"])

                        result = SKILL_REGISTRY[tool_name](**args_to_pass)
                        _send_response(req_id, {"content": [{"type": "text", "text": str(result)}]})
                    except Exception as exc:
                        _send_response(req_id, {"content": [{"type": "text", "text": f"Error: {exc}"}]})
                else:
                    _send_error(req_id, -32601, "Tool not found")
        except json.JSONDecodeError:
            pass


if __name__ == "__main__":
    serve_mcp()
