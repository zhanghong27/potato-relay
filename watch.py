#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from urllib import request


DEFAULT_RELAY = "http://127.0.0.1:8787"
DEFAULT_STATE_DIR = Path.home() / ".hermes" / "potato-relay" / "watch-state"
DEFAULT_INBOX_DIR = Path.home() / ".hermes" / "potato-relay" / "inbox"


def post_json(url: str, payload: dict, timeout: int = 10) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def read_state(path: Path) -> int:
    try:
        return int(json.loads(path.read_text()).get("last_id", 0))
    except Exception:
        return 0


def write_state(path: Path, last_id: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"last_id": last_id}, ensure_ascii=False, indent=2))


def append_inbox(path: Path, messages: list[dict]) -> None:
    if not messages:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for msg in messages:
            fh.write(
                f"\n## #{msg['id']} {msg['created_at']} {msg['sender']} -> {msg['recipient']}\n\n"
                f"{msg['text']}\n"
            )


def run_command(template: str, recipient: str, messages: list[dict]) -> None:
    if not template or not messages:
        return
    payload = json.dumps({"recipient": recipient, "messages": messages}, ensure_ascii=False)
    subprocess.run(template.format(recipient=recipient, json=payload), shell=True, check=False)


def poll_once(args: argparse.Namespace) -> list[dict]:
    state_path = Path(args.state_dir) / f"{args.recipient}.json"
    since_id = read_state(state_path)
    result = post_json(
        f"{args.relay.rstrip('/')}/api/messages/read",
        {
            "recipient": args.recipient,
            "exclude_sender": args.sender or args.recipient,
            "since_id": since_id,
            "limit": args.limit,
        },
    )
    messages = result.get("messages", [])
    if messages:
        last_id = max(int(m["id"]) for m in messages)
        write_state(state_path, last_id)
        append_inbox(Path(args.inbox_dir) / f"{args.recipient}.md", messages)
        run_command(args.on_message, args.recipient, messages)
    return messages


def main() -> None:
    parser = argparse.ArgumentParser(description="Poll Potato Relay cheaply and persist new inbox messages")
    parser.add_argument("--recipient", required=True, help="Agent name to watch, e.g. 清蒸土豆 or 麻辣土豆丝")
    parser.add_argument("--sender", default="", help="Own sender name to exclude; defaults to recipient")
    parser.add_argument("--relay", default=DEFAULT_RELAY)
    parser.add_argument("--interval", type=float, default=20.0)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    parser.add_argument("--inbox-dir", default=str(DEFAULT_INBOX_DIR))
    parser.add_argument("--once", action="store_true")
    parser.add_argument(
        "--on-message",
        default="",
        help="Optional shell command template run only when new messages arrive. Fields: {recipient}, {json}",
    )
    args = parser.parse_args()

    while True:
        messages = poll_once(args)
        for msg in messages:
            print(f"#{msg['id']} {msg['sender']} -> {msg['recipient']}: {msg['text']}", flush=True)
        if args.once:
            return
        time.sleep(max(args.interval, 1.0))


if __name__ == "__main__":
    main()
