# Lab 11: Finding an agent to call

## What the video showed
Before your agent hands a job to another agent, it needs that agent's card. The standard place to look is the agent's own domain at `/.well-known/agent-card.json`; a registry or your own configuration are other ways to get it. Your agent reads the card the way it will use it, then creates its client from the card.

## Run it
```
python lab11_discover.py
```
It starts a stand-in agent on a free local port, reads its card, creates a client and stops. Sample output: `out/lab11.txt`.

## What to look for
- `[1]`: `A2ACardResolver(httpx_client=..., base_url=URL).get_agent_card()` fetches the card from the well-known path. You give it only the base address.
- `[2]`: the skill check looks for a skill tagged `route-planning`. If no skill matches the job, this agent is the wrong one to call.
- `[3]`: content types. A skill can list its own `input_modes`/`output_modes`; when it doesn't, the card's `default_input_modes`/`default_output_modes` apply.
- `[4]`: `capabilities.streaming` and `capabilities.push_notifications` tell you whether you can stream or get callbacks from this agent.
- `[5]`: the card's `security_requirements` point at `security_schemes`. Here it's OpenID Connect with scopes `openid` and `profile`. Getting that token is done with the identity provider, outside A2A. (The stand-in doesn't check the token. A real agent would.)
- `[6]`: the card lists `HTTP+JSON` first and `JSONRPC` second. The client here supports only JSON-RPC (the SDK default), so it skips the first entry and uses the first one it supports. The code reads the private `_transport` attribute only to show you which one it picked.

## Try this
- Change `JOB_TAG` to `'translation'` and run again: step `[2]` reports no matching skill.
- In `create_client`, pass `ClientConfig(..., supported_protocol_bindings=['HTTP+JSON', 'JSONRPC'])`. The client now supports both, so it takes the card's first entry, `RestTransport` at `/rest`.
