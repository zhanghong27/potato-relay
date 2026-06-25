#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path
from urllib import request


DEFAULT_RELAY = "http://127.0.0.1:8787"
DEFAULT_STATE_DIR = Path.home() / ".hermes" / "potato-relay" / "watch-state"
DEFAULT_INBOX_DIR = Path.home() / ".hermes" / "potato-relay" / "inbox"
DEFAULT_LOCK_DIR = Path.home() / ".hermes" / "potato-relay" / "locks"
DEFAULT_TRIGGER_STATE_DIR = Path.home() / ".hermes" / "potato-relay" / "trigger-state"


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


def split_aliases(value: str, fallback: str) -> set[str]:
    aliases = {part.strip() for part in str(value or "").split(",") if part.strip()}
    if fallback:
        aliases.add(fallback)
    return aliases


def is_addressed_to_agent(msg: dict, aliases: set[str]) -> bool:
    recipient = str(msg.get("recipient") or "").strip()
    text = str(msg.get("text") or "")
    if recipient in aliases:
        return True
    if recipient == "all" and any(alias and alias in text for alias in aliases):
        return True
    return False


def read_json(path: Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def is_cooling_down(path: Path, seconds: float) -> bool:
    if seconds <= 0:
        return False
    payload = read_json(path, {})
    last_ts = float(payload.get("last_trigger_ts") or 0)
    return last_ts > 0 and time.time() - last_ts < seconds


def write_cooldown(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"last_trigger_ts": time.time()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def acquire_lock(path: Path, stale_seconds: float = 3600) -> int | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        return os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            if time.time() - path.stat().st_mtime > stale_seconds:
                path.unlink()
                return os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except OSError:
            return None
    return None


def release_lock(path: Path, fd: int | None) -> None:
    if fd is None:
        return
    try:
        os.close(fd)
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def build_prompt(args: argparse.Namespace, messages: list[dict]) -> str:
    agent_name = args.agent_name or args.recipient
    reply_sender = args.reply_sender or agent_name
    aliases = ", ".join(sorted(split_aliases(args.aliases, args.recipient)))
    payload = json.dumps(
        {
            "recipient": args.recipient,
            "agent_name": agent_name,
            "aliases": sorted(split_aliases(args.aliases, args.recipient)),
            "messages": messages,
        },
        ensure_ascii=False,
        indent=2,
    )
    return f"""你是 {agent_name}，本机土豆中转站 watcher 发现有新消息点名你。

只处理下面 JSON 里列出的新消息，不要重复读取历史消息。你的名字/别名是：{aliases}。

处理规则：
1. 只有消息确实发给你，或正文明确叫到你的名字/别名时，才需要回复。
2. 如果需要对方继续处理，把 recipient 写成对方名字，例如“清蒸土豆”或“酸辣土豆丝/麻辣土豆丝”。
3. 除非用户明确要求多轮讨论，否则这批消息最多产生一条中转站回复，避免两个 agent 无限互相接话。
4. 视频相关内容优先使用消息里的本地路径，不要上传视频；涉及高成本视频生成/重生成时，按你的成本控制规则先判断是否需要用户确认。
5. 如果不需要回复，输出 ignore。

你最后必须只输出一个 JSON 对象，不要 Markdown，不要解释文字：
{{"action":"reply","sender":"{reply_sender}","recipient":"对方名字","text":"回复正文"}}

如果不需要回复，输出：
{{"action":"ignore","sender":"{reply_sender}","recipient":"","text":""}}

新消息 JSON：
{payload}
"""


def strip_ansi(value: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", value)


def extract_json_object(output: str) -> dict | None:
    clean = strip_ansi(output).strip()
    if not clean:
        return None

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean, re.DOTALL)
    candidates = [fenced.group(1)] if fenced else []
    candidates.append(clean)

    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        starts = [idx for idx, char in enumerate(candidate) if char == "{"]
        for start in reversed(starts):
            try:
                parsed, _ = decoder.raw_decode(candidate[start:])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and "action" in parsed:
                return parsed
    return None


def post_reply(args: argparse.Namespace, reply: dict) -> None:
    action = str(reply.get("action") or "").strip().lower()
    if action in {"ignore", "none", "noop", ""}:
        print("Hermes trigger returned ignore; no relay reply posted.", flush=True)
        return
    if action != "reply":
        print(f"Hermes trigger returned unsupported action: {action}", flush=True)
        return

    sender = str(reply.get("sender") or args.reply_sender or args.agent_name or args.recipient).strip()
    recipient = str(reply.get("recipient") or "").strip()
    text = str(reply.get("text") or "").strip()
    if not sender or not recipient or not text:
        print("Hermes trigger reply missing sender, recipient, or text; skipped.", flush=True)
        return

    if args.dry_run:
        print(
            "DRY RUN relay post: "
            + json.dumps({"sender": sender, "recipient": recipient, "text": text}, ensure_ascii=False),
            flush=True,
        )
        return

    result = post_json(
        f"{args.relay.rstrip('/')}/api/messages",
        {"sender": sender, "recipient": recipient, "text": text},
    )
    msg = result.get("message", {})
    print(f"Posted relay reply #{msg.get('id')} {sender} -> {recipient}", flush=True)


def trigger_hermes(args: argparse.Namespace, messages: list[dict]) -> bool:
    if not args.hermes_command or not messages:
        return False

    lock_path = Path(args.lock_dir) / f"{args.recipient}.lock"
    cooldown_path = Path(args.trigger_state_dir) / f"{args.recipient}.json"
    if is_cooling_down(cooldown_path, args.cooldown):
        print(f"Trigger for {args.recipient} is cooling down; messages remain pending.", flush=True)
        return False

    fd = acquire_lock(lock_path)
    if fd is None:
        print(f"Trigger for {args.recipient} is already running; messages remain pending.", flush=True)
        return False

    try:
        write_cooldown(cooldown_path)
        prompt = build_prompt(args, messages)
        cmd = [
            args.hermes_command,
            "chat",
            "-Q",
            "--accept-hooks",
            "--source",
            "potato-relay",
            "--max-turns",
            str(args.max_turns),
            "-q",
            prompt,
        ]
        print(f"Triggering {args.hermes_command} for {args.recipient} with {len(messages)} message(s).", flush=True)
        if args.dry_run:
            print("DRY RUN command: " + json.dumps(cmd, ensure_ascii=False), flush=True)
            return True

        env = os.environ.copy()
        env.setdefault("HOME", str(Path.home()))
        env.setdefault("HERMES_ACCEPT_HOOKS", "1")
        launchd_path = (
            f"{Path.home()}/.local/bin:"
            "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        )
        env["PATH"] = f"{launchd_path}:{env.get('PATH', '')}" if env.get("PATH") else launchd_path
        proc = subprocess.run(
            cmd,
            cwd=str(Path.home()),
            env=env,
            text=True,
            capture_output=True,
            timeout=args.trigger_timeout,
            check=False,
        )
        if proc.stdout:
            print(proc.stdout.rstrip(), flush=True)
        if proc.stderr:
            print(proc.stderr.rstrip(), flush=True)
        if proc.returncode != 0:
            print(f"Hermes trigger exited with code {proc.returncode}; message will be retried later.", flush=True)
            return False

        reply = extract_json_object(proc.stdout)
        if reply is None:
            print("Hermes trigger did not return a parseable JSON object; no relay reply posted.", flush=True)
            return True
        post_reply(args, reply)
        return True
    except subprocess.TimeoutExpired:
        print(f"Hermes trigger timed out after {args.trigger_timeout}s; message will be retried later.", flush=True)
        return False
    finally:
        release_lock(lock_path, fd)


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
        aliases = split_aliases(args.aliases, args.recipient)
        addressed_messages = [msg for msg in messages if is_addressed_to_agent(msg, aliases)]
        if args.hermes_command and addressed_messages and not trigger_hermes(args, addressed_messages):
            return []

        last_id = max(int(m["id"]) for m in messages)
        write_state(state_path, last_id)
        append_inbox(Path(args.inbox_dir) / f"{args.recipient}.md", messages)
        if args.hermes_command:
            if not addressed_messages:
                print(f"No new messages addressed to {args.recipient}; state advanced to #{last_id}.", flush=True)
        else:
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
    parser.add_argument("--lock-dir", default=str(DEFAULT_LOCK_DIR))
    parser.add_argument("--trigger-state-dir", default=str(DEFAULT_TRIGGER_STATE_DIR))
    parser.add_argument("--aliases", default="", help="Comma-separated names that should wake this agent")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Print trigger/post actions without calling Hermes or posting")
    parser.add_argument(
        "--on-message",
        default="",
        help="Optional shell command template run only when new messages arrive. Fields: {recipient}, {json}",
    )
    parser.add_argument("--hermes-command", default="", help="Path to hermes/video-critic command for automatic wakeups")
    parser.add_argument("--agent-name", default="", help="Human-readable agent name used in the wakeup prompt")
    parser.add_argument("--reply-sender", default="", help="Sender name to use when watcher posts a JSON reply")
    parser.add_argument("--max-turns", type=int, default=30)
    parser.add_argument("--trigger-timeout", type=float, default=1800)
    parser.add_argument("--cooldown", type=float, default=0, help="Minimum seconds between automatic wakeups per recipient")
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
