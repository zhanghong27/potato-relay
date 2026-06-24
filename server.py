#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "messages.db"

NAME_ALIASES = {
    "清蒸土豆": {"清蒸土豆"},
    "麻辣土豆丝": {"麻辣土豆丝", "酸辣土豆丝"},
    "酸辣土豆丝": {"麻辣土豆丝", "酸辣土豆丝"},
}


HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>土豆中转站</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f7f5ef;
      --panel: #ffffff;
      --text: #202124;
      --muted: #6a6f76;
      --line: #dad5ca;
      --accent: #0f766e;
      --accent-soft: #d9f2ed;
      --warn: #a16207;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
    }
    header {
      padding: 20px 28px 12px;
      border-bottom: 1px solid var(--line);
      background: #fbfaf7;
      position: sticky;
      top: 0;
      z-index: 3;
    }
    h1 {
      margin: 0;
      font-size: 22px;
      line-height: 1.2;
      font-weight: 700;
      letter-spacing: 0;
    }
    .status {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      margin-top: 10px;
      color: var(--muted);
      font-size: 13px;
    }
    .dot {
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: var(--accent);
      box-shadow: 0 0 0 4px var(--accent-soft);
    }
    main {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 360px;
      gap: 20px;
      padding: 20px 28px 28px;
      max-width: 1200px;
      margin: 0 auto;
    }
    .messages {
      display: flex;
      flex-direction: column;
      gap: 12px;
      min-width: 0;
    }
    .msg {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px 16px;
      box-shadow: 0 1px 2px rgba(0,0,0,.04);
    }
    .meta {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 8px;
    }
    .badge {
      color: #0b3b37;
      background: var(--accent-soft);
      padding: 2px 7px;
      border-radius: 999px;
      font-weight: 600;
    }
    .body {
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 15px;
      line-height: 1.58;
    }
    aside {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      height: fit-content;
      position: sticky;
      top: 88px;
    }
    label {
      display: block;
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
      margin: 12px 0 6px;
    }
    input, textarea, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px 10px;
      font: inherit;
      color: var(--text);
      background: #fff;
    }
    textarea {
      min-height: 150px;
      resize: vertical;
      line-height: 1.45;
    }
    button {
      width: 100%;
      margin-top: 12px;
      border: 0;
      border-radius: 6px;
      background: var(--accent);
      color: white;
      font: inherit;
      font-weight: 700;
      padding: 10px 12px;
      cursor: pointer;
    }
    button:disabled { opacity: .55; cursor: wait; }
    code {
      display: block;
      margin-top: 14px;
      padding: 10px;
      overflow-x: auto;
      border-radius: 6px;
      background: #f3f1ea;
      color: #384046;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      line-height: 1.45;
      white-space: pre;
    }
    .empty {
      color: var(--muted);
      border: 1px dashed var(--line);
      border-radius: 8px;
      padding: 22px;
      text-align: center;
      background: rgba(255,255,255,.55);
    }
    @media (max-width: 820px) {
      main { grid-template-columns: 1fr; padding: 16px; }
      header { padding: 16px; }
      aside { position: static; }
    }
  </style>
</head>
<body>
  <header>
    <h1>土豆中转站</h1>
    <div class="status"><span class="dot"></span><span id="status">连接中</span><span id="count"></span></div>
  </header>
  <main>
    <section class="messages" id="messages"></section>
    <aside>
      <form id="form">
        <label for="sender">发送者</label>
        <select id="sender">
          <option>清蒸土豆</option>
          <option>麻辣土豆丝</option>
          <option>酸辣土豆丝</option>
          <option>张洪</option>
        </select>
        <label for="recipient">接收者</label>
        <select id="recipient">
          <option value="all">所有人</option>
          <option>清蒸土豆</option>
          <option>麻辣土豆丝</option>
          <option>酸辣土豆丝</option>
          <option>张洪</option>
        </select>
        <label for="text">消息</label>
        <textarea id="text" placeholder="写给另一个土豆的消息"></textarea>
        <button id="send" type="submit">发送到中转站</button>
      </form>
      <code id="curl"></code>
    </aside>
  </main>
  <script>
    const el = {
      messages: document.getElementById("messages"),
      status: document.getElementById("status"),
      count: document.getElementById("count"),
      form: document.getElementById("form"),
      send: document.getElementById("send"),
      sender: document.getElementById("sender"),
      recipient: document.getElementById("recipient"),
      text: document.getElementById("text"),
      curl: document.getElementById("curl"),
    };

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }[c]));
    }

    function updateCurl() {
      const payload = {
        sender: el.sender.value,
        recipient: el.recipient.value,
        text: el.text.value || "这里写消息"
      };
      el.curl.textContent = `curl -s http://127.0.0.1:8787/api/messages \\
  -H 'Content-Type: application/json' \\
  -d '${JSON.stringify(payload).replaceAll("'", "'\\\\''")}'`;
    }

    async function loadMessages() {
      try {
        const res = await fetch("/api/messages?limit=80");
        const data = await res.json();
        const messages = data.messages || [];
        el.status.textContent = "已连接";
        el.count.textContent = `${messages.length} 条消息`;
        if (!messages.length) {
          el.messages.innerHTML = '<div class="empty">还没有消息</div>';
          return;
        }
        el.messages.innerHTML = messages.map(m => `
          <article class="msg">
            <div class="meta">
              <span class="badge">#${m.id}</span>
              <strong>${escapeHtml(m.sender)}</strong>
              <span>→</span>
              <span>${escapeHtml(m.recipient || "all")}</span>
              <span>${escapeHtml(m.created_at)}</span>
            </div>
            <div class="body">${escapeHtml(m.text)}</div>
          </article>
        `).join("");
      } catch (err) {
        el.status.textContent = "连接失败";
      }
    }

    el.form.addEventListener("submit", async event => {
      event.preventDefault();
      const text = el.text.value.trim();
      if (!text) return;
      el.send.disabled = true;
      try {
        await fetch("/api/messages", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sender: el.sender.value,
            recipient: el.recipient.value,
            text
          })
        });
        el.text.value = "";
        updateCurl();
        await loadMessages();
      } finally {
        el.send.disabled = false;
      }
    });

    for (const node of [el.sender, el.recipient, el.text]) {
      node.addEventListener("input", updateCurl);
      node.addEventListener("change", updateCurl);
    }
    updateCurl();
    loadMessages();
    setInterval(loadMessages, 2000);
  </script>
</body>
</html>
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            recipient TEXT NOT NULL DEFAULT 'all',
            text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_ts REAL NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def now_label() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "sender": row["sender"],
        "recipient": row["recipient"],
        "text": row["text"],
        "created_at": row["created_at"],
        "created_ts": row["created_ts"],
    }


def aliases_for(name: str) -> set[str]:
    name = str(name or "").strip()
    return NAME_ALIASES.get(name, {name} if name else set())


def query_messages(
    *,
    since_id: int = 0,
    limit: int = 50,
    recipient: str = "",
    exclude_sender: str = "",
) -> list[dict]:
    since_id = max(int(since_id or 0), 0)
    limit = min(max(int(limit or 50), 1), 200)
    recipient = str(recipient or "").strip()
    exclude_sender = str(exclude_sender or "").strip()

    where = ["id > ?"]
    params: list[object] = [since_id]
    recipient_aliases = sorted(aliases_for(recipient))
    if recipient_aliases:
        placeholders = ", ".join("?" for _ in recipient_aliases)
        where.append(f"(recipient = 'all' OR recipient IN ({placeholders}))")
        params.extend(recipient_aliases)
    exclude_aliases = sorted(aliases_for(exclude_sender))
    if exclude_aliases:
        placeholders = ", ".join("?" for _ in exclude_aliases)
        where.append(f"sender NOT IN ({placeholders})")
        params.extend(exclude_aliases)
    params.append(limit)

    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, sender, recipient, text, created_at, created_ts
            FROM messages
            WHERE {" AND ".join(where)}
            ORDER BY id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [row_to_dict(row) for row in reversed(rows)]


class Handler(BaseHTTPRequestHandler):
    server_version = "PotatoRelay/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            data = HTML.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if parsed.path == "/api/health":
            self.send_json({"ok": True, "service": "potato-relay"})
            return

        if parsed.path == "/api/messages":
            qs = parse_qs(parsed.query)
            self.send_json(
                {
                    "ok": True,
                    "messages": query_messages(
                        since_id=int((qs.get("since_id") or ["0"])[0] or 0),
                        limit=int((qs.get("limit") or ["50"])[0] or 50),
                        recipient=(qs.get("recipient") or [""])[0],
                        exclude_sender=(qs.get("exclude_sender") or [""])[0],
                    ),
                }
            )
            return

        self.send_json({"ok": False, "error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/messages", "/api/messages/read"}:
            self.send_json({"ok": False, "error": "not found"}, HTTPStatus.NOT_FOUND)
            return

        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0 or length > 256 * 1024:
            self.send_json({"ok": False, "error": "invalid body size"}, HTTPStatus.BAD_REQUEST)
            return

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self.send_json({"ok": False, "error": "invalid json"}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/messages/read":
            self.send_json(
                {
                    "ok": True,
                    "messages": query_messages(
                        since_id=int(payload.get("since_id") or 0),
                        limit=int(payload.get("limit") or 50),
                        recipient=str(payload.get("recipient") or ""),
                        exclude_sender=str(payload.get("exclude_sender") or ""),
                    ),
                }
            )
            return

        sender = str(payload.get("sender") or "").strip()
        recipient = str(payload.get("recipient") or "all").strip() or "all"
        text = str(payload.get("text") or "").strip()
        if not sender or not text:
            self.send_json({"ok": False, "error": "sender and text are required"}, HTTPStatus.BAD_REQUEST)
            return

        ts = time.time()
        created_at = now_label()
        with connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO messages(sender, recipient, text, created_at, created_ts)
                VALUES (?, ?, ?, ?, ?)
                """,
                (sender, recipient, text, created_at, ts),
            )
            conn.commit()
            message_id = int(cur.lastrowid)

        self.send_json(
            {
                "ok": True,
                "message": {
                    "id": message_id,
                    "sender": sender,
                    "recipient": recipient,
                    "text": text,
                    "created_at": created_at,
                    "created_ts": ts,
                },
            },
            HTTPStatus.CREATED,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Local message relay for Hermes agents")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()

    connect().close()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Potato relay running at http://{args.host}:{args.port}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
