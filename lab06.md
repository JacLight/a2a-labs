# Lab 06: The smallest A2A server

## What the video showed
To offer your agent you publish an Agent Card and run an A2A server. The SDK handles the protocol; you write the executor, the code that runs when a job arrives.

## Run it
```
python lab06_serve.py
```
It starts its own server on a free local port, sends one message, prints the reply and stops. Sample output: `out/lab06.txt`.

## What to look for
- `[1]`: one server, two addresses: the card at `/.well-known/agent-card.json` (served by `create_agent_card_routes`) and the JSON-RPC endpoint at `/` (served by `create_jsonrpc_routes`).
- In the code, `DefaultRequestHandler(agent_executor=..., task_store=InMemoryTaskStore(), agent_card=card)` is the SDK part. You don't write any protocol handling.
- `HelloExecutor.execute` is your part: it creates a task, calls `HelloAgent().invoke(...)`, adds the result as an artifact and sets the task to completed.
- `[3]`: the caller gets back a task in `TASK_STATE_COMPLETED` with the agent's text as its artifact.
- `HelloAgent` stands for your agent. It could be built with any framework, or none.

## Try this
- Change the text that `HelloAgent.invoke` returns, run again, and see it in the `artifact:` line.
- Send `'how are you'` instead of `'hi'` (the second example listed on the card's skill).
