# Lab 20: Securing your agent

## What the video showed
Three decisions: how callers sign in, what each caller may do, and what your card shows. Credentials travel with each request, not inside the A2A message. One caller can't see or cancel another caller's tasks, and such a task looks the same as one that doesn't exist.

## Run it
```
python lab20_secure.py
```
Sample output: `out/lab20.txt`. The tokens in the file are labelled examples. The lab runs plain HTTP on 127.0.0.1 only; the spec says production deployments MUST use encryption (HTTPS).

## What to look for
- `[1]` the public card lists the sign-in method (`securitySchemes`). This lab uses an HTTP bearer token as one example; a card can instead (or also) list an API key, OAuth 2.0, OpenID Connect or mutual TLS.
- `[2]` a SendMessage with no `Authorization` header gets `HTTP 401` before it reaches the A2A handler. That's `BearerCheck`, plain Starlette middleware in front of the routes.
- The token goes in an HTTP header on every request (`as_caller` puts it on the `httpx` client), never in the message.
- `[3]` bob asking for alice's task, bob cancelling it, and bob asking for a made-up ID all get the same `TaskNotFoundError: Task not found`.
- The comment above `handler`: the SDK's `InMemoryTaskStore` scopes tasks by the signed-in user's name by default. Your own rules (per skill, action, data) can be added on top.

## Try this
- Give bob alice's token in `as_caller(...)` and see `bob gets alice's task` turn into `ok`. The server only knows callers by their credentials.
- Add a third example token for a new caller to `EXAMPLE_TOKENS`, create a task as that caller, and check alice can't see it.
