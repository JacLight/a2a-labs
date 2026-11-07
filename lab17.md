# Lab 17: Live updates with streaming

## What the video showed
To stream, check that the card supports it and send with streaming on. In the Python SDK, that's one setting on the client. The stream starts with the task, then brings a status update when the state changes and an artifact update when output is ready. Large outputs can arrive in pieces, with flags for "add this to the same artifact" and "this is the last piece". If the connection drops, subscribe to the task again: first you get the task as it is now, then the updates continue.

## Run it
```
python lab17_stream.py
```
Sample output: `out/lab17.txt`.

## What to look for
- `[1]` and `ClientConfig(..., streaming=True)`: the one setting. The SDK streams only if the card's `capabilities.streaming` is true too.
- `[2]`: the order is the same as in the official Hello World tutorial: `task SUBMITTED`, `status update WORKING "Processing request..."`, artifact updates, `status update COMPLETED`. Then the stream closes.
- The three artifact updates carry `append=False/True` and `last_chunk=True` on the last one. `show()` adds pieces to the same `artifact_id` when `append` is true.
- `[3]`: the client stops reading after the first piece and closes the stream (`await stream.aclose()`). The task keeps running on the agent.
- `(resubscribed) task WORKING (artifact so far: "Hello, World! ")`: after `client.subscribe(...)`, the first event is the task snapshot, which already includes the piece sent while the client was away. Then the remaining updates arrive.

## Try this
- Make the stand-in ask a question before the artifacts (`await up.requires_input(new_text_message('Which language?', task_id=task.id, context_id=task.context_id)); return`). The stream in `[2]` ends at `INPUT_REQUIRED`.
- In `[3]`, change `asyncio.sleep(0.6)` to `asyncio.sleep(2)`. The task has finished before you subscribe, and the subscription is refused with `UnsupportedOperationError ... is in terminal state` (wrap it in `try`/`except` to print it). For a finished task, use `get_task` instead.
