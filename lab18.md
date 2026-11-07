# Lab 18: Callbacks with push notifications

## What the video showed
Check that the card supports push notifications, then give the remote agent a webhook address and the credentials it should use when it calls you, in the first message or added to a task later. The agent sends updates to your webhook (the same kind of update a stream carries), and your webhook replies with a success code. The same update can arrive twice, and one can go missing. So check the credentials, check that the task ID is one you started, ignore duplicates, then fetch the task. If you offer push notifications, the spec recommends checking the webhook addresses callers give you.

## Run it
```
python lab18_push.py
```
It runs two local servers: the stand-in agent and your webhook receiver. Sample output: `out/lab18.txt`.

## What to look for
- `[2]`: the push config goes in the first message: `TaskPushNotificationConfig(url=WEBHOOK, authentication=AuthenticationInfo(scheme='Bearer', credentials=SECRET))`. With `return_immediately=True` the task comes back `SUBMITTED` and no connection stays open.
- `webhook()` checks the `Authorization` header first. A call with the wrong credentials gets `401`. Everything else gets `200` straight away and is checked afterwards in `check()`.
- `[3]`: each notification is a StreamResponse: `task`, `statusUpdate` or `artifactUpdate`. The fake call about `"not-mine"` is ignored because it isn't a task this client started.
- `statusUpdate duplicate, ignored`: the stand-in's `RetryingSender` sends the final update twice, as a retry would. The client recognises the same body and drops it. Then `GetTask` fetches the full result.
- `[4]`, agent side: the SDK's `validate_push_notification_url` rejects private, link-local and loopback addresses, and registering `http://192.168.1.10/hook` fails with `InvalidParamsError`. The lab's own webhook is on 127.0.0.1, so `allowed()` allow-lists that one exact address (see the comment there).

## Try this
- In `[2]`, change `credentials=SECRET` to `credentials='wrong'` and run again. The agent's calls now get `401`, nothing reaches `[3]` except the fake call, and the SDK logs each failed delivery. `GetTask` still gets the result.
- Add the webhook to the task after it exists instead: send without `task_push_notification_config`, then set `push.task_id = task.id` and call `await client.create_task_push_notification_config(push)`. Notifications sent before you registered (here, the first `task` one) don't reach you.
