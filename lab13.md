# Lab 13: The states your code handles

## What the video showed
Once you have a task, your code branches on its state, in four cases. Keep waiting: submitted, working. Paused, needs you: input required, auth required. Collect: completed. It's over: failed, canceled, rejected. Completed, failed, canceled and rejected are final, and a message sent to a final task gets an error. A waiting call also returns at a pause, not only at the end.

## Run it
```
python lab13_states.py
```
It takes about 6 seconds. Sample output: `out/lab13.txt`.

## What to look for
- `follow()` is the four-way switch. `KEEP_WAITING`, `PAUSED`, `COMPLETED` and `OVER` match the four cases in the video.
- `[1]`: six jobs, one per path. Each line shows the states the loop saw and what it did: `collect`, `paused, needs you` (with the question from the status message), or `it's over`.
- The `slow` job is cancelled by the client while it's `WORKING`, so it ends `CANCELED`.
- `[2]`: a default (waiting) call on a job that asks a question returns after about 0.7 s at `INPUT_REQUIRED`, before the job is done. Your code has to handle pauses as well as endings.
- `[3]`: a message sent to the completed task is refused with `UnsupportedOperationError ... is in terminal state: TASK_STATE_COMPLETED`.
- The two `logging` lines near the end hide a cleanup traceback that a2a-sdk 1.3.0 prints on the server side after `[3]`. They don't change what the client sees.

## Try this
- In `[3]`, send the message to the paused task from `[2]` (`task_id=task.id, context_id=task.context_id`) instead of `done`. It's accepted, and the same task completes, because a paused task isn't final.
- Remove `'slow'` from the job list and `return_immediately=True` from the first loop. The calls now wait, so each line starts at the final or paused state. (`'slow'` is removed because a waiting call on it would block until the job ends.)
