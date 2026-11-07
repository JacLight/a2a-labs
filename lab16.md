# Lab 16: Getting the results

## What the video showed
When a task completes, its artifacts are the output, and each one can hold text, files or data. The agent's messages are progress and questions; the agent decides which it keeps in the task's history, so don't count on finding one there later. You can fetch a task by ID with as much recent history as you want, up to what the agent keeps. You can list the tasks you've started, filtered by conversation or state, newest first.

## Run it
```
python lab16_results.py
```
Sample output: `out/lab16.txt`.

## What to look for
- `[1]`: three artifacts, each with a different kind of part: `url` (a file by link, `image/png`), `data` (`application/json`) and `text`.
- `[2]`: with `historyLength` not set you get everything this agent kept (your message plus two progress messages). `1` gives the most recent one; `0` gives none. `historyLength` is a maximum, and an agent may return fewer.
- `[2]`: the last message, "Done.", is the current status message. In this SDK it isn't in the history list. That's one reason not to rely on history for results.
- `[3]`: `ListTasks(context_id=...)` returns `b` then `a`, newest first. `ListTasks(status=INPUT_REQUIRED)` finds only the paused task `c`.
- `[3]`: with `page_size=2` you get one page and a `next_page_token`. Artifacts are left out unless you set `include_artifacts=True`.
- You see only the tasks the agent's rules let you see. The SDK's in-memory store keys tasks by the caller's identity; this lab has a single caller, so it sees all of them.

## Try this
- Pass the `next_page_token` back as `page_token=` to fetch the second page (task `a`).
- Set `include_artifacts=True` on the `page_size=2` call and check the `artifacts included:` value.
