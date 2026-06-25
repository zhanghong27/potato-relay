# Potato Relay / 土豆中转站

本地 HTTP 消息中转站，用来绕开飞书等平台不让机器人互相读取消息的问题。

它提供：

- 一个本地网页：查看和手动发送消息
- 一个 JSON API：让多个 agent 通过 `POST/GET` 写入和读取消息
- SQLite 持久化：消息存到本地 `messages.db`
- 零依赖：只使用 Python 标准库

启动：

```bash
python3 server.py
```

网页：

```text
http://127.0.0.1:8787
```

发送消息：

```bash
curl -s http://127.0.0.1:8787/api/messages \
  -H 'Content-Type: application/json' \
  -d '{"sender":"清蒸土豆","recipient":"酸辣土豆丝","text":"我完成了初版，请审查。"}'
```

读取消息：

```bash
curl -s http://127.0.0.1:8787/api/messages/read \
  -H 'Content-Type: application/json' \
  -d '{"recipient":"酸辣土豆丝","exclude_sender":"酸辣土豆丝","since_id":0}'
```

建议两个 agent 记住各自最后读到的 `id`，下一次用 `since_id=<最后的 id>` 增量拉取。

## Name Addressing

Agent 只应处理发给自己的消息：

- `清蒸土豆` 处理 `recipient=清蒸土豆`
- `麻辣土豆丝` 和 `酸辣土豆丝` 视为同一个 critic agent 的别名

需要对方回复时，把 `recipient` 写成对方名字。不要靠普通正文暗示。

## Efficient Polling

见 [POLLING.md](POLLING.md)。基础方式是用 `watch.py` 做本地轻量轮询，只在有新消息时写入本地 inbox，不在空轮询时调用模型：

```bash
python3 watch.py --recipient 清蒸土豆 --interval 20
python3 watch.py --recipient 麻辣土豆丝 --sender 酸辣土豆丝 --interval 20
```

如果要让 agent 被点名时自动醒来，启用 `--hermes-command`：

```bash
python3 watch.py --recipient 清蒸土豆 --interval 20 \
  --aliases 清蒸土豆 \
  --hermes-command /Users/zhanghong/.local/bin/hermes \
  --agent-name 清蒸土豆 \
  --reply-sender 清蒸土豆 \
  --cooldown 45
```

Auto-wake 只在消息发给该 agent，或 `recipient=all` 且正文点名它时调用模型。空轮询仍然只是本地 HTTP + SQLite。

## Local Video Path Protocol

When both agents run on the same machine, do not upload videos to the relay. Send local file paths in the message body instead.

Recommended review request:

```text
酸辣土豆丝，请审查这个视频。

video_path: /Users/zhanghong/.../final_v3.mp4
script_path: /Users/zhanghong/.../script_v3.md
subtitle_path: /Users/zhanghong/.../final_v3.srt
voiceover_path: /Users/zhanghong/.../voiceover_v3.mp3
focus:
- 检查事实准确性
- 检查画面和旁白是否一致
- 给出 must_fix 和 fix_type
time_range: 全片 / 00:00-00:15
```

This avoids duplicate storage and keeps cost focused on analysis, not transfer.

## macOS LaunchAgent

仓库里有 `launchd.plist.example`。复制到 `~/Library/LaunchAgents/` 后，把里面的脚本路径改成你的实际路径，再运行：

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.example.potato-relay.plist
```

## Security

默认只监听 `127.0.0.1`，只适合本机 agent 使用。不要在公网暴露这个服务，除非你自己加认证。
