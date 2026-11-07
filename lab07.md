# Lab 07: Writing your Agent Card

## What the video showed
Callers read your card to decide whether to send you a job: your skills, the content you take and return, the extras you support, where you can be reached and how to sign in. Extra details for signed-in callers go in an extended card.

## Run it
```
python lab07_agent_card.py
```
Sample output: `out/lab07.txt`.

## What to look for
- `[1]` fetches the card with plain `httpx`, with no A2A library on the caller side. It's just JSON at `/.well-known/agent-card.json`.
- The numbered comments `# 1.` to `# 5.` in the card code match the card's parts: skills (name, description, examples), content types (`text/plain`), capabilities (`streaming`, `pushNotifications`, `extendedAgentCard`), the interface (`JSONRPC`, URL, A2A `1.0`) and the sign-in scheme.
- `sign-in:` shows one HTTP bearer scheme. That's one of several kinds a card can list (API key, HTTP auth, OAuth 2.0, OpenID Connect, mutual TLS).
- `[2]` without a token the extended card request gets HTTP 401; `[3]` with the example token it returns the extended card with the extra skill `Echo Bot (Super Mode)`.
- The comment above `BearerCheck`: the spec says the extended card MUST require authentication, but the SDK serves it to any request that reaches the route. Here the check is done by plain Starlette middleware.

## Try this
- Add a second public skill to `card` (a new `AgentSkill`) and see it appear in `[1]`.
- Change `default_output_modes` to `['application/json']` and check the `takes/returns` line.
