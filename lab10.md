# Lab 10: Serving over more than one binding

## What the video showed
A binding is the concrete format the A2A calls travel in: JSON-RPC, gRPC or HTTP+JSON. You can offer several, list them in your card with your preferred one first, and a caller uses the first one on that list that it supports. The SDK's routes plug into an ordinary web app.

## Run it
```
python lab10_bindings.py
```
Sample output: `out/lab10.txt`. gRPC is left out: the SDK's gRPC handler needs the `grpcio` package, which this lab doesn't install.

## What to look for
- `[card]`: two interfaces in order, JSON-RPC first (preferred), HTTP+JSON second. Both are served by the same `handler` through `create_jsonrpc_routes` and `create_rest_routes`.
- `[A]` lists HTTP+JSON first in its own preferences, but the card's order decides, so the server sees `POST /jsonrpc`.
- `[B]` only supports HTTP+JSON, so it takes the second interface: the server sees `POST /rest/message:send`.
- All three replies are the same. Same executor, same result, whichever binding carried it.
- `log_requests` is ordinary Starlette middleware. Because the SDK gives you routes, logging (and authentication, lab 20) stay under your control.

## Try this
- Swap the two `AgentInterface` entries in the card. Caller A and caller B then both use HTTP+JSON; caller C still uses JSON-RPC.
- Add `use_client_preference=True` to the `ClientConfig` in `caller()`. Caller A then follows its own list and uses HTTP+JSON. (The SDK's own docs recommend the server's order in most cases.)
