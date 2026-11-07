# Lab 23: Versions and extensions

## What the video showed
A client sends the A2A version it speaks with every request (current: 1.0); an agent that doesn't support it returns an error instead of guessing. Extensions are listed in the card, a client opts in per request, and if a required extension isn't declared the agent returns an error.

## Run it
```
python lab23_versions.py
```
Sample output: `out/lab23.txt`.

## What to look for
- `[1]` raw requests with different `A2A-Version` headers: `1.0` works, `0.5` gets error `-32009` (VersionNotSupportedError in the JSON-RPC binding). Each raw request also sends `A2A-Extensions` for citations, so the required-extension check passes.
- `[1]` also shows two things a2a-sdk 1.3.0 really does (explained in the comment under the loop). No header is read as `0.3`, as the spec says, and refused because this server doesn't serve 0.3. And `1.1` is accepted: 1.3.0 compares only the major number, while the spec talks about matching Major.Minor.
- `[2]` the SDK client adds `A2A-Version: 1.0` by itself (the agent's reply prints the header it saw). The opt-in goes in the `A2A-Extensions` header via `ClientCallContext(service_parameters=...)`, and the location data rides in the message `metadata` under the extension's URI.
- The card's `capabilities.extensions` lists both extensions, using the spec's example URIs; marking citations `required=True` is this lab's choice.
- `[3]` opting in to geolocation only gets `ExtensionSupportRequiredError`. Note the comment in `Researcher.execute`: 1.3.0 passes the opted-in URIs to your code but does not enforce "required" itself, so this check is written by hand.

## Try this
- Set the citations extension to `required=False` and run again: `[3]` now succeeds.
- Add `'2.0'` to the version list in `[1]` and see it refused with `-32009` as well.
