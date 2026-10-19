"""Testler için küçük stdio MCP sunucusu (gerçek ağ/program yok).

Araçlar: `topla` (okuma), `dosya_yaz` (yazma — gerçekte dosyaya dokunmaz), `yavas`
(zaman aşımı denemesi), `hata` (isError=true). Sunucu ilk araç listesinden önce istemciye
`ping` gönderir (sunucu→istemci isteği yanıtlanıyor mu?), stdout'a bir log satırı yazar
(istemci JSON olmayan satırı yok saymalı) ve stderr'e Türkçe günlük yazar.
Seçenek: argv[1] == "coker" → initialize'dan sonra çıkar.
"""
import json
import sys
import time

MODE = sys.argv[1] if len(sys.argv) > 1 else ""

TOOLS = [
    {"name": "topla", "description": "İki sayıyı toplar.",
     "inputSchema": {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                     "required": ["a", "b"]},
     "annotations": {"readOnlyHint": True}},
    {"name": "dosya_yaz", "description": "Bir dosyaya yazar (sahte).",
     "inputSchema": {"type": "object", "properties": {"yol": {"type": "string"}}, "required": ["yol"]},
     "annotations": {"readOnlyHint": True}},     # yalan söylüyor: istemci buna güvenmemeli
    {"name": "yavas", "description": "Uzun sürer.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "hata", "description": "Hata döndürür.", "inputSchema": {"type": "object", "properties": {}}},
]


def send(msg):
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stderr.write("sahte sunucu başladı · ğüşıöç\n")
    sys.stderr.flush()
    pinged = False
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        method, rid = msg.get("method"), msg.get("id")
        if rid is None:                      # bildirim
            if method == "notifications/initialized" and not pinged:
                print("bu bir log satırı, JSON değil", flush=True)
                send({"jsonrpc": "2.0", "id": "srv-1", "method": "ping"})
                pinged = True
            continue
        if "result" in msg or "error" in msg:  # bizim ping'imizin yanıtı
            continue
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": msg["params"]["protocolVersion"],
                "capabilities": {"tools": {}}, "serverInfo": {"name": "sahte", "version": "1"}}})
            if MODE == "coker":
                sys.exit(3)
        elif method == "tools/list":
            cursor = (msg.get("params") or {}).get("cursor")
            if not cursor:
                send({"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS[:2], "nextCursor": "s2"}})
            else:
                send({"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS[2:]}})
        elif method == "tools/call":
            name = msg["params"]["name"]
            args = msg["params"].get("arguments") or {}
            if name == "topla":
                send({"jsonrpc": "2.0", "id": rid, "result": {
                    "content": [{"type": "text", "text": f"Toplam: {args['a'] + args['b']} · ğüş"}]}})
            elif name == "dosya_yaz":
                send({"jsonrpc": "2.0", "id": rid, "result": {
                    "content": [{"type": "text", "text": f"yazıldı: {args.get('yol')}"}]}})
            elif name == "yavas":
                time.sleep(5)
                send({"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": "geç"}]}})
            else:
                send({"jsonrpc": "2.0", "id": rid, "result": {
                    "content": [{"type": "text", "text": "bir şey ters gitti"}], "isError": True}})
        else:
            send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "yok"}})


if __name__ == "__main__":
    main()
