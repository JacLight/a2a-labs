# Lab 08: Handling a job

## What the video showed
You write an agent executor with two methods, `execute` and `cancel`. In `execute` you get or create the task, set it to working with a short status message, run your agent, add the result as an artifact and set it to completed. A streaming caller sees each step; a non-streaming caller gets the final task. A quick answer can be a single message, with no task.

## Run it
```
python lab08_executor.py
```
Sample output: `out/lab08.txt`.

## What to look for
- `[1]` the streaming caller receives four things in order: the new task (`SUBMITTED`), `WORKING` with "Processing request...", the artifact, then `COMPLETED` with "Request is completed!".
- Each of those lines comes from one line of `HelloExecutor.execute`: `enqueue_event(task)`, `update_status(WORKING)`, `add_artifact(...)`, `update_status(COMPLETED)`.
- `[2]` the non-streaming caller sends the same message and gets one task, already completed, with the artifact inside. The SDK gathered the steps for it.
- `[3]` for `"ping"` the executor enqueues a `Message` instead of a task, and the caller gets that message.
- `[4]` lists the tasks in the store: only the two "hi" jobs are there. The "ping" reply made no task.

## Try this
- Delete the `update_status(state=TaskState.TASK_STATE_WORKING, ...)` call and see the streaming caller get one event fewer.
- Set `AgentCapabilities(streaming=False)` on the card. The SDK client then doesn't stream, so `[1]` prints a single completed task like `[2]`.
