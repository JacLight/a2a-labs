# Lab 19: Cancelling, and follow-ups

## What the video showed
To stop a job, cancel the task. It's a request, and the agent may not be able to stop. If it can, you get the task back, now canceled. If it can't, for example because the task already finished, you get an error. A finished task can't be reopened. Instead, send a new message with the same context ID and list the earlier task in the message's reference task IDs. The agent answers with a new task (or just a message) and can build on what came before.

## Run it
```
python lab19_cancel_followup.py
```
Sample output: `out/lab19.txt`.

## What to look for
- `[1]`: `client.cancel_task(CancelTaskRequest(id=...))` on a `WORKING` task returns the task with state `CANCELED`.
- `[2]`: the same call on a `COMPLETED` task raises `TaskNotCancelableError: Task cannot be canceled`.
- `[3]`: a new message to the finished task (same task ID) is refused with `UnsupportedOperationError ... is in terminal state`.
- `[4]`: the follow-up is built with `context_id=first.context_id` and `follow.reference_task_ids.append(first.id)`. It creates a new task ID in the same context.
- The stand-in's answer quotes the earlier tagline. The SDK looked up the referenced task and handed it to the executor as `ctx.related_tasks`, because the handler was created with `SimpleRequestContextBuilder(should_populate_referred_tasks=True, ...)`.
- The context ID was created by the agent. The client reuses it as given and treats it as an opaque value.

## Try this
- In `[4]`, leave out `reference_task_ids`. You still get a new task in the same context, but the stand-in no longer sees the earlier task.
- Make the stand-in answer follow-ups with a Message (`await q.enqueue_event(new_text_message(..., context_id=ctx.context_id))` before creating a task). Then handle `reply.message` in `send()`.
