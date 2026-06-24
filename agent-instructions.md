# 给 Hermes Agent 的使用说明

你可以通过本地土豆中转站与另一个 agent 沟通，不依赖飞书是否能读机器人消息。

服务地址：

```text
http://127.0.0.1:8787
```

发送消息给另一个 agent：

```bash
curl -s http://127.0.0.1:8787/api/messages \
  -H 'Content-Type: application/json' \
  -d '{"sender":"你的名字","recipient":"对方名字","text":"消息内容"}'
```

读取发给你的消息：

```bash
curl -s http://127.0.0.1:8787/api/messages/read \
  -H 'Content-Type: application/json' \
  -d '{"recipient":"你的名字","exclude_sender":"你的名字","since_id":0}'
```

规则：

- 只有用户明确要求你和另一个 agent 沟通时，才主动使用中转站。
- 每次读取后记住最大 `id`，下次用 `since_id=<最大 id>`，避免重复处理旧消息。
- 回复对方时，把 `recipient` 设置成对方名字；广播时才用 `all`。
