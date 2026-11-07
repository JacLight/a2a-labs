# Lab 15: When it needs a login or an approval

## What the video showed
In auth required, the remote agent needs permission to continue, and its status message says what it needs. The credential normally doesn't travel inside an A2A message. It reaches the agent by a separate, secure route, such as an OAuth sign-in, unless both sides have agreed on another way. Once it arrives, the agent may carry on without any message from you, so keep listening. The state itself grants nothing: what the credential allows is decided by the agent and whoever issued it.

## Run it
```
python lab15_auth_required.py
```
Sample output: `out/lab15.txt`.

## What to look for
- `[1]`: the waiting call returns at the pause, `AUTH_REQUIRED`, with the status message naming the need ("an OAuth access token for the Calendar API").
- `[2]`: the client keeps listening by subscribing to the task (`streamer.subscribe(SubscribeToTaskRequest(id=...))`). The first thing on the stream is the task as it is now. Keeping a stream open, push notifications, or checking the task with `get_task` would also work.
- `[3]` is a stand-in. The `POST /oauth/callback` is a plain HTTP route on the agent, outside A2A, standing in for a real OAuth sign-in. It is not an A2A message, and the A2A client never puts the token in a message.
- `[4]`: with no message from the client, the stream brings `WORKING`, the artifact, then `COMPLETED`, and closes.
- In `CalendarAgent.execute`, the agent checks the token itself (`'calendar.read' in ISSUED.get(token, ...)`) before reading the calendar. Reaching `AUTH_REQUIRED` and getting *a* token isn't enough.

## Try this
- Send `'access_token': 'wrong-token'` in `[3]`. The agent's own check fails the task, and the stream ends with `FAILED`.
- Replace the subscription with a loop that calls `client.get_task(...)` every 0.3 s until the state is final. That's the "keep checking" option.
