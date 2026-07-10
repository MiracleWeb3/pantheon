#!/usr/bin/env python3
"""pantheon MCP server — lets a dispatched subagent reach the store directly.

Only the UserPromptSubmit hook can recall/save today; a subagent has no way
to ask "what do we know about X?". This exposes the same store operations
over MCP stdio so any agent can call them mid-task.

Protocol: JSON-RPC 2.0, one message per line on stdin/stdout (MCP stdio is
newline-delimited, NOT Content-Length framed). stdlib only, no MCP SDK.

Tools: pantheon_recall, pantheon_lesson_add, pantheon_receipt_add,
pantheon_stats — thin wrappers over lib/store.py, scoped to the cwd's
project key like the hooks already do.

PANTHEON_DB_PATH env var overrides the store location (tests only; real
sessions use the default ~/.claude/pantheon/pantheon.db).

Self-check: python3 mcp_server.py --selftest
"""
import sys, os, json, time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "lib"))
import store, paths


class RpcError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


TOOLS = [
    {
        "name": "pantheon_recall",
        "description": "Recall past pantheon lessons relevant to a query.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "text to match past lessons against"},
                "limit": {"type": "integer", "description": "max lessons to return (<=5)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "pantheon_lesson_add",
        "description": "Save a lesson to the pantheon memory store.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "the lesson text"},
                "tags": {"type": "string", "description": "comma-separated tags"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "pantheon_receipt_add",
        "description": "File a receipt recording what a discipline/skill did.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "skill": {"type": "string", "description": "discipline/skill name"},
                "note": {"type": "string", "description": "what happened, one line"},
            },
            "required": ["skill", "note"],
        },
    },
    {
        "name": "pantheon_stats",
        "description": "Store counts and top disciplines from the last 7 days.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _connect():
    return store.connect(os.environ.get("PANTHEON_DB_PATH", ""))


def _keys():
    return paths.project_name(os.getcwd())


def tool_recall(args):
    conn = _connect()
    hits = store.recall(conn, args.get("query", ""), keys=_keys(),
                        limit=min(int(args.get("limit") or 3), 5))
    conn.close()
    if not hits:
        return "no lessons clear the relevance bar for that query"
    return "\n".join(f"({h['source']}) {h['text']}" for h in hits)


def tool_lesson_add(args):
    conn = _connect()
    lid = store.add_lesson(conn, args.get("text", ""), tags=args.get("tags", ""),
                           keys=_keys(), source="mcp")
    conn.close()
    return f"lesson #{lid} saved" if lid else "duplicate"


def tool_receipt_add(args):
    conn = _connect()
    rid = store.add_receipt(conn, args.get("skill", ""), args.get("note", ""),
                            session=os.environ.get("CLAUDE_SESSION_ID", ""), project=_keys())
    conn.close()
    return f"receipt #{rid} filed"


def tool_stats(args):
    conn = _connect()
    c = store.counts(conn)
    rows = conn.execute(
        "SELECT skill, COUNT(*) n FROM receipts WHERE ts>? GROUP BY skill "
        "ORDER BY n DESC LIMIT 6", (time.time() - 7 * 86400,)).fetchall()
    conn.close()
    out = (f"store: {c['lessons']} lessons · {c['receipts']} receipts · "
           f"{c['routes']} routes · {c['metrics']} metrics")
    if rows:
        out += "\n7d disciplines: " + " · ".join(f"{r['skill']}×{r['n']}" for r in rows)
    return out


TOOL_FUNCS = {"pantheon_recall": tool_recall, "pantheon_lesson_add": tool_lesson_add,
              "pantheon_receipt_add": tool_receipt_add, "pantheon_stats": tool_stats}


def _plugin_version():
    try:
        with open(os.path.join(_ROOT, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
            return json.load(f).get("version", "0")
    except Exception:
        return "0"


def _tools_call(params):
    name = params.get("name")
    fn = TOOL_FUNCS.get(name)
    if not fn:
        raise RpcError(-32602, f"unknown tool: {name}")
    return {"content": [{"type": "text", "text": fn(params.get("arguments") or {})}]}


def _dispatch(req):
    if not isinstance(req, dict):
        raise RpcError(-32600, "invalid request")
    method = req.get("method")
    if method == "initialize":
        return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                "serverInfo": {"name": "pantheon", "version": _plugin_version()}}
    if method == "notifications/initialized":
        return {}  # no reply anyway — it's a notification (no id)
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        return _tools_call(req.get("params") or {})
    raise RpcError(-32601, f"method not found: {method}")


def _write(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            _write({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
            continue
        has_id = isinstance(req, dict) and "id" in req
        try:
            result, err = _dispatch(req), None
        except RpcError as e:
            result, err = None, (e.code, str(e))
        except Exception as e:
            result, err = None, (-32603, f"internal error: {e}")
        if not has_id:
            continue  # notifications get no reply, success or not
        if err:
            _write({"jsonrpc": "2.0", "id": req.get("id"), "error": {"code": err[0], "message": err[1]}})
        else:
            _write({"jsonrpc": "2.0", "id": req.get("id"), "result": result})


def selftest() -> int:
    import subprocess, tempfile
    dbp = os.path.join(tempfile.mkdtemp(prefix="pantheon-mcp-"), "t.db")
    env = dict(os.environ, PANTHEON_DB_PATH=dbp)
    proc = subprocess.Popen([sys.executable, os.path.abspath(__file__)],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, bufsize=1, env=env)

    def send(obj):
        proc.stdin.write(json.dumps(obj) + "\n")
        proc.stdin.flush()

    def recv():
        return json.loads(proc.stdout.readline())

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        r = recv()
        assert r["id"] == 1 and r["result"]["serverInfo"]["name"] == "pantheon", r

        send({"jsonrpc": "2.0", "method": "notifications/initialized"})  # no id, no reply

        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        r = recv()
        assert r["id"] == 2 and len(r["result"]["tools"]) == 4, r

        send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
              "params": {"name": "pantheon_lesson_add",
                        "arguments": {"text": "mcp selftest lesson: pipes work end to end",
                                     "tags": "selftest"}}})
        r = recv()
        assert r["id"] == 3 and "saved" in r["result"]["content"][0]["text"], r

        send({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
              "params": {"name": "pantheon_recall",
                        "arguments": {"query": "does the mcp selftest prove pipes work end to end?"}}})
        r = recv()
        assert r["id"] == 4 and "pipes work" in r["result"]["content"][0]["text"], r

        send({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
              "params": {"name": "pantheon_stats", "arguments": {}}})
        r = recv()
        assert r["id"] == 5 and "lessons" in r["result"]["content"][0]["text"], r

        send({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
              "params": {"name": "nope", "arguments": {}}})
        r = recv()
        assert r["id"] == 6 and r["error"]["code"] == -32602, r

        send({"jsonrpc": "2.0", "id": 7, "method": "bogus/method", "params": {}})
        r = recv()
        assert r["id"] == 7 and r["error"]["code"] == -32601, r
    finally:
        proc.stdin.close()
        proc.wait(timeout=5)

    print("selftest ok — initialize, tools/list x4, lesson_add + recall round trip, "
          "stats, unknown tool/method errors")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    main()
