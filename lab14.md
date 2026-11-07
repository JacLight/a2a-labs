# Lab 14: When the remote agent asks you a question

## What the video showed
When a task comes back as input required, read the question in its status message and answer with a new message that carries the same task ID. The same task then carries on. A2A doesn't say who answers. Leave the task ID off and your answer isn't attached to that task. Send a context ID that doesn't match the task's and the agent rejects the message.

## Run it
```
python lab14_answer_question.py
```
Sample output: `out/lab14.txt`.

## What to look for
- `[1]`: "Book me a flight" comes back `INPUT_REQUIRED` with the question in `task.status.message`, as in the spec's example.
- `on_question()` is where the answer comes from. Here it's plain code; it could be your agent's model or a person you pass the question to.
- `[2]`: the answer is sent with `task_id=task.id, context_id=task.context_id`. The same task ID comes back, now `COMPLETED`, with the booking as its artifact.
- `[3]`: the same answer without the task ID (with the right context ID) lands in a different, new task. The stand-in treats it as a fresh request and asks again. The first task is still `INPUT_REQUIRED`.
- `[4]`: task ID plus a context ID that isn't the task's is rejected with `InvalidParamsError: Context ... does not match context ... of task ...`. The spec says agents MUST reject this.

## Try this
- In `[2]`, send only `task_id=task.id` (no `context_id`). It still works: the agent MUST infer the context from the task.
- Change `on_question` to read the answer from the keyboard with `input(question + ' ')`, so a person answers.
