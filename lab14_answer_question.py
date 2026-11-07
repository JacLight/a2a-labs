"""Lab 14 (video section s14): when the remote agent asks you a question.

The task comes back INPUT_REQUIRED with the question in its status message. You
answer with a new message carrying the same task ID, and the same task carries on.
Leave the task ID off and the answer isn't attached to that task; send a context ID
that doesn't match the task's and the agent rejects it.
Run: python lab14_answer_question.py
"""
import asyncio, socket
import httpx, uvicorn
from starlette.applications import Starlette
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import get_message_text, new_task_from_user_message, new_text_message, new_text_part
from a2a.server.agent_execution import AgentExecutor
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (AgentCapabilities, AgentCard, AgentInterface, AgentSkill, GetTaskRequest,
                       Role, SendMessageRequest, TaskState)

# --- your agent: the client side ---
st = lambda t: TaskState.Name(t.status.state).removeprefix('TASK_STATE_')

async def on_question(question):
    # A2A doesn't say who answers: your agent's model, your own code, or a person.
    # Here it's plain code.
    return 'From San Francisco to New York'

async def send(client, text, task_id=None, context_id=None):
    msg = new_text_message(text, role=Role.ROLE_USER, task_id=task_id, context_id=context_id)
    return [r async for r in client.send_message(SendMessageRequest(message=msg))][-1].task

async def main():
    async with httpx.AsyncClient(timeout=10) as http:
        card = await A2ACardResolver(http, URL).get_agent_card()
        client = await create_client(card, client_config=ClientConfig(httpx_client=http, streaming=False))

        print('[1] send "Book me a flight"')
        task = await send(client, 'Book me a flight')         # the call returns at the pause
        print(f'    task {task.id[:8]}.. {st(task)}: "{get_message_text(task.status.message)}"')

        print('[2] answer with the same task ID (and its context ID)')
        answer = await on_question(get_message_text(task.status.message))
        after = await send(client, answer, task_id=task.id, context_id=task.context_id)
        print(f'    task {after.id[:8]}.. {st(after)}  same task: {after.id == task.id}')
        print(f'    artifact: "{after.artifacts[0].parts[0].text}"')

        print('[3] answer WITHOUT the task ID (same context ID)')
        first = await send(client, 'Book me a flight')
        other = await send(client, answer, context_id=first.context_id)
        print(f'    reply went to task {other.id[:8]}.. ({st(other)})  same task: {other.id == first.id}')
        first = await client.get_task(GetTaskRequest(id=first.id))
        print(f'    first task {first.id[:8]}.. is still {st(first)}')

        print("[4] answer with the task ID but a context ID that isn't the task's")
        try:
            await send(client, answer, task_id=first.id, context_id='some-other-conversation')
            print('    accepted (unexpected)')
        except Exception as e:
            print(f'    rejected: {type(e).__name__}: {e}'.replace(first.id, first.id[:8] + '..')
                  .replace(first.context_id, first.context_id[:8] + '..'))
        await client.close()

# --- the remote agent (stand-in) ---
# A new request is paused with a question; an answer on the same task completes it.
class FlightBooker(AgentExecutor):
    async def execute(self, ctx, q):
        task = ctx.current_task
        if task is None:                                       # a new request
            task = new_task_from_user_message(ctx.message); await q.enqueue_event(task)
            up = TaskUpdater(q, task.id, task.context_id)
            await up.start_work()
            await up.requires_input(new_text_message(
                'I need more details. Where would you like to fly from and to?',
                task_id=task.id, context_id=task.context_id))
            return
        up = TaskUpdater(q, task.id, task.context_id)          # the answer, on the same task
        await up.start_work()
        await asyncio.sleep(0.3)
        await up.add_artifact([new_text_part(f'Booked: {get_message_text(ctx.message)}')], name='booking')
        await up.complete()
    async def cancel(self, ctx, q): pass

with socket.socket() as s:
    s.bind(('127.0.0.1', 0)); PORT = s.getsockname()[1]
URL = f'http://127.0.0.1:{PORT}'
card = AgentCard(name='Flight Booker', description='Books flights.', version='1.0.0',
    default_input_modes=['text/plain'], default_output_modes=['text/plain'],
    capabilities=AgentCapabilities(streaming=False),
    supported_interfaces=[AgentInterface(protocol_binding='JSONRPC', url=URL, protocol_version='1.0')],
    skills=[AgentSkill(id='book', name='Book a flight', description='Books a flight.', tags=['travel'])])
handler = DefaultRequestHandler(agent_executor=FlightBooker(), task_store=InMemoryTaskStore(), agent_card=card)
app = Starlette(routes=[*create_agent_card_routes(card), *create_jsonrpc_routes(handler, '/')])

# --- run both, then shut down ---
async def run():
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=PORT, log_level='warning'))
    serving = asyncio.create_task(server.serve())
    while not server.started: await asyncio.sleep(0.05)
    try: await main()
    finally:
        await handler.aclose(); server.should_exit = True; await serving

asyncio.run(run())
