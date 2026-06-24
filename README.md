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

## macOS LaunchAgent

仓库里有 `launchd.plist.example`。复制到 `~/Library/LaunchAgents/` 后，把里面的脚本路径改成你的实际路径，再运行：

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.example.potato-relay.plist
```

## Security

默认只监听 `127.0.0.1`，只适合本机 agent 使用。不要在公网暴露这个服务，除非你自己加认证。
