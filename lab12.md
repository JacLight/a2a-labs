# Lab 12: Sending the job

## What the video showed
A job goes out as a message made of parts: text, a file (as bytes or a link) or structured data, each with an optional media type. What comes back is either a Message or a Task. The remote agent decides which, so your code handles both. By default the call waits; with `returnImmediately` you get the task back as soon as it exists and follow it yourself. `acceptedOutputModes` tells the agent which media types you accept.

## Run it
```
python lab12_message_or_task.py
```
Sample output: `out/lab12.txt`.

## What to look for
- `show(reply)` is the "handle both" code: `reply.HasField('message')` means a direct answer with nothing to track; otherwise `reply.task` has an `id` and a `context_id`.
- `[1]`: a plain question gets a Message back. That was the stand-in's choice; another agent could have made a task.
- `[2]`: one message, three parts: `text`, `raw` (the image bytes, `image/png`, with a filename) and `data`. Use `new_url_part(...)` instead of `new_raw_part(...)` to send a file as a link.
- `[3]`: the default call took about 1.2 s and came back `COMPLETED`. It waits until the task finishes or pauses.
- `[4]`: with `return_immediately=True` the task came back at once as `SUBMITTED`. The loop then checks it with `get_task` until it is final (`SUBMITTED -> WORKING -> COMPLETED`). Checking is one way to follow a task; streaming and push notifications are covered in labs 17 and 18.
- `[3]` vs `[4]`: the stand-in reads `accepted_output_modes` and returns a `data` part for `application/json` and a `text` part for `text/plain`. Agents SHOULD use this to tailor their output. It's a hint, not a guarantee.

## Try this
- In `[3]`, set `return_immediately=True` and watch the `after ...s` time drop to 0.0 and the state change to `SUBMITTED`.
- Remove the `new_raw_part(...)` line from the job and see the stand-in answer with a Message instead of a Task.
