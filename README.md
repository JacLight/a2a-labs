# A2A labs

Short, runnable tutorials that go with the video "A2A: Agent-to-Agent Protocols, in depth". Each lab shows one section of the
video working, using the official Python SDK (a2a-sdk 1.3.0). Every lab starts its own server on a free local port
(127.0.0.1 only), runs, prints what happened and stops. Nothing is sent outside your machine.

## Set up once
```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run a lab
```
python lab06_serve.py
```
Each lab has a tutorial (`labNN.md`: what the video showed, what to look for, what to try) and a sample of its output (`out/labNN.txt`).

| Lab | What it shows | File |
|---|---|---|
| 06 | The smallest A2A server | `lab06_serve.py` |
| 07 | Writing your Agent Card | `lab07_agent_card.py` |
| 08 | Handling a job | `lab08_executor.py` |
| 09 | Stopping to ask, and cancels | `lab09_pause_and_cancel.py` |
| 10 | Serving over more than one binding | `lab10_bindings.py` |
| 11 | Finding an agent to call | `lab11_discover.py` |
| 12 | Sending the job | `lab12_message_or_task.py` |
| 13 | The states your code handles | `lab13_states.py` |
| 14 | When the remote agent asks you a question | `lab14_answer_question.py` |
| 15 | When it needs a login or an approval | `lab15_auth_required.py` |
| 16 | Getting the results | `lab16_results.py` |
| 17 | Live updates with streaming | `lab17_stream.py` |
| 18 | Callbacks with push notifications | `lab18_push.py` |
| 19 | Cancelling, and follow-ups | `lab19_cancel_followup.py` |
| 20 | Securing your agent | `lab20_secure.py` |
| 23 | Versions and extensions | `lab23_versions.py` |

Where the SDK and the spec differ, the lab says so in a comment and in its tutorial. gRPC is left out (it needs extra packages);
lab 10 shows JSON-RPC and HTTP+JSON. The tokens in lab 20 are labelled examples, and the labs use plain HTTP on your own
machine only: the spec says production deployments must use HTTPS.

Lab 06 and lab 07 are adapted from the official A2A Hello World sample (github.com/a2aproject/a2a-samples). Facts come from the
official A2A 1.0 specification (github.com/a2aproject/A2A) and docs (a2a-protocol.org).

Open `index.html` in a browser to read every lab, its code and its sample output on one page.
