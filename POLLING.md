# Efficient Agent Polling

Goal: let agents see relay messages quickly without spending model calls on empty checks.

## Recommended Policy

1. Agents only reply through Potato Relay when addressed by their own name.
   - 清蒸土豆 handles messages addressed to `清蒸土豆`.
   - 麻辣土豆丝 / 酸辣土豆丝 handles messages addressed to either alias.
2. If a reply from the other agent is needed, address that agent by name in `recipient`.
3. Do not create endless back-and-forth. One message should usually produce at most one reply unless the user asks for a discussion.
4. For video review, send local file paths instead of uploading/copying the video.

## Cost-Effective Visibility

Use a cheap local watcher for each agent:

```bash
python3 watch.py --recipient 清蒸土豆 --interval 20
python3 watch.py --recipient 麻辣土豆丝 --sender 酸辣土豆丝 --interval 20
```

The watcher:

- calls the local relay API every N seconds;
- stores `last_id` in `~/.hermes/potato-relay/watch-state/`;
- appends new messages to `~/.hermes/potato-relay/inbox/<agent>.md`;
- does not call an LLM unless you explicitly pass `--on-message`.

This means idle polling is almost free. Model cost happens only when a user calls an agent or when you intentionally configure an on-message command.

## Local Video Path Review

Because the agents run on the same Mac mini, the relay should carry paths, not video bytes:

```text
video_path: /Users/zhanghong/.../final_v3.mp4
script_path: /Users/zhanghong/.../script_v3.md
subtitle_path: /Users/zhanghong/.../final_v3.srt
voiceover_path: /Users/zhanghong/.../voiceover_v3.mp3
focus:
- Check factual accuracy
- Check visual/audio/script alignment
time_range: 00:00-00:15
```

Cost-effective critic order:

1. Read script/subtitle/voiceover text and metadata first.
2. If `time_range` is provided, inspect only that section.
3. Extract key frames only when text/metadata is insufficient.
4. Avoid full-video visual analysis unless explicitly requested or necessary.

## Optional Trigger Mode

If you later want fully automatic agent wakeups, use `--on-message` with a command that starts the relevant Hermes profile. Keep a cooldown/debounce outside the model to avoid loops.

Example shape:

```bash
python3 watch.py --recipient 麻辣土豆丝 --sender 酸辣土豆丝 --interval 20 \
  --on-message 'video-critic chat -Q -q "你在土豆中转站收到新消息：{json}。只有消息点名你时才回复，需要清蒸土豆回复时 recipient 写清蒸土豆。"'
```

Use trigger mode sparingly. The default watcher-only mode is the better price/performance choice.
