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
- does not call an LLM unless you explicitly enable `--hermes-command` or `--on-message`.

This means idle polling is almost free. Model cost happens only when a message is actually addressed to an agent.

## Auto-Wake Mode

Use auto-wake when you want the agents to notice relay messages without being reminded in Feishu:

```bash
python3 watch.py --recipient 清蒸土豆 --interval 20 \
  --aliases 清蒸土豆 \
  --hermes-command /Users/zhanghong/.local/bin/hermes \
  --agent-name 清蒸土豆 \
  --reply-sender 清蒸土豆 \
  --cooldown 45

python3 watch.py --recipient 麻辣土豆丝 --sender 酸辣土豆丝 --interval 20 \
  --aliases 酸辣土豆丝,麻辣土豆丝 \
  --hermes-command /Users/zhanghong/.local/bin/video-critic \
  --agent-name 酸辣土豆丝 \
  --reply-sender 酸辣土豆丝 \
  --cooldown 45
```

Auto-wake behavior:

- direct `recipient` matches wake the agent;
- `recipient=all` only wakes the agent if the message text contains one of its aliases;
- the watcher asks Hermes for one final JSON object;
- the watcher posts that JSON reply back to the relay, so the agent does not need to run `curl`;
- if the agent returns `{"action":"ignore"}`, nothing is posted;
- a per-agent lock and cooldown prevent overlapping or runaway wakeups.

Run `watch.py --help` for testing options. `--dry-run --once` is useful for checking the trigger command without spending model tokens.

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

## Legacy Shell Trigger

`--on-message` is still available for custom shell integrations, but `--hermes-command` is safer for this relay because it avoids shell quoting issues and lets the watcher post replies itself.
