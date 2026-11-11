"""Cliente mínimo del MCP de ActivePieces (JSON-RPC sobre SSE).
Uso: AP_TOKEN=$(python3 -c "import json;print(json.load(open('/opt/data/secrets/ap_jonathan.token'))['token'])")
"""
import json, os, urllib.request, uuid

URL = os.environ.get("AP_MCP_URL", "http://100.73.30.29:8088/mcp")
TOK = os.environ["AP_TOKEN"]


def rpc(method, params=None, timeout=240):
    body = json.dumps({"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": method, "params": params or {}}).encode()
    req = urllib.request.Request(URL, data=body, method="POST")
    req.add_header("Authorization", "Bearer " + TOK)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode()
    if raw.strip().startswith("event:"):
        return json.loads("\n".join(l[5:].strip() for l in raw.splitlines() if l.startswith("data:")))
    return json.loads(raw)


def call(name, args, timeout=240):
    res = rpc("tools/call", {"name": name, "arguments": args}, timeout)
    if "error" in res:
        return {"ERROR": res["error"]}
    c = res.get("result", {})
    if c.get("content"):
        txt = "".join(x.get("text", "") for x in c["content"] if x.get("type") == "text")
        try:
            return json.loads(txt)
        except Exception:
            return txt
    return c
