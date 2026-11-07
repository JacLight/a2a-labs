# Lab 09: Stopping to ask, and cancels

## What the video showed
When your agent needs more from the caller, set the task to input required with the question in the status message. The answer comes back on the same task and `execute` runs again. When a caller cancels, the SDK calls your `cancel` method. There you can try to stop the work and set the task to canceled, or refuse.

## Run it
```
python lab09_pause_and_cancel.py
```
Sample output: `out/lab09.txt`. It takes well under a second, even though the "long job" would sleep for 60 seconds: the cancel stops it.

## What to look for
- `[1]` the task stops at `TASK_STATE_INPUT_REQUIRED` and its status message is the question (the one from the official LangGraph currency sample).
- `[2]` the answer `"EUR"` is sent with the same task ID (see `send(client, 'EUR', task)`); the same task ID then shows `COMPLETED` with the result.
- `[3]` is way 1. `Converter.cancel` sets `TASK_STATE_CANCELED`, and the caller gets the canceled task back.
- `[4]` is way 2. `RefusingConverter.cancel` raises `UnsupportedOperationError` (the 1.3.0 way of writing the LangGraph sample's refusal). What a2a-sdk 1.3.0 does with that: the caller gets `TaskNotCancelableError`, and the task is left `FAILED`. That is this SDK's behaviour, shown as it really runs.
- Both copies of the agent run in one Starlette app on two paths (`/stops`, `/refuses`) so you can compare them.

## Try this
- Make `RefusingConverter.cancel` raise `NotImplementedError('Cancel is not supported.')` like the Hello World sample. In 1.3.0 the caller then gets `InternalError` instead.
- Change the question text in the `INPUT_REQUIRED` branch, or answer `"JPY"` in step `[2]`.
