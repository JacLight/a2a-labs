"""Lab 13 (video section s13): the states your code handles.

Your code branches on the task's state, in four cases:
  keep waiting (submitted, working) · paused, needs you (input required, auth required)
  collect (completed) · it's over (failed, canceled, rejected).
Completed, failed, canceled and rejected are final: a message sent to a final task
gets an error. A waiting call returns at a pause, not only at the end.
Run: python lab13_states.py
"""
import asyncio, logging, socket, time
import httpx, uvicorn
from starlette.applications import Starlette
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import get_message_text, new_task_from_user_message, new_text_message, new_text_part
from a2a.server.agent_execution import AgentExecutor
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (AgentCapabilities, AgentCard, AgentInterface, AgentSkill, CancelTaskRequest,
                       GetTaskRequest, Role, SendMessageConfiguration, SendMessageRequest, TaskState as S)

# --- your agent: the client side ---
KEEP_WAITING = {S.TASK_STATE_SUBMITTED, S.TASK_STATE_WORKING}
PAUSED = {S.TASK_STATE_INPUT_REQUIRED, S.TASK_STATE_AUTH_REQUIRED}
OVER = {S.TASK_STATE_FAILED, S.TASK_STATE_CANCELED, S.TASK_STATE_REJECTED}
name = lambda s: S.Name(s).removeprefix('TASK_STATE_')

async def follow(client, task, stop=False):
    """The four-way switch. Returns the states seen and what the code did."""
    seen = []
    while True:
        s = task.status.state
        if not seen or seen[-1] != name(s): seen.append(name(s))
        if s in KEEP_WAITING:                       # keep waiting: check again shortly
            if stop and s == S.TASK_STATE_WORKING:  # (for the 'slow' job, we cancel it here)
                await client.cancel_task(CancelTaskRequest(id=task.id))
            await asyncio.sleep(0.2)
            task = await client.get_task(GetTaskRequest(id=task.id)); continue
        if s in PAUSED:                             # can't finish until you act
            return seen, f'paused, needs you: "{get_message_text(task.status.message)}"'
        if s == S.TASK_STATE_COMPLETED:             # collect the artifacts
            return seen, f'collect: {[a.name for a in task.artifacts]}'
        if s in OVER:                               # error, stopped, or turned down
            why = get_message_text(task.status.message) if task.status.HasField('message') else ''
            return seen, f"it's over {why}".rstrip()

async def send(client, text, **config):
    req = SendMessageRequest(message=new_text_message(text, role=Role.ROLE_USER),
                             configuration=SendMessageConfiguration(**config))
    return [r async for r in client.send_message(req)][-1].task

async def main():
    async with httpx.AsyncClient(timeout=10) as http:
        card = await A2ACardResolver(http, URL).get_agent_card()
        client = await create_client(card, client_config=ClientConfig(httpx_client=http, streaming=False))

        print('[1] one loop, every state (each job sent with returnImmediately, then checked)')
        done = None
        for job in ['summarise Q3', 'ask', 'login', 'break', 'refuse', 'slow']:
            task = await send(client, job, return_immediately=True)
            seen, action = await follow(client, task, stop=(job == 'slow'))
            print(f'    {job:<13} {" > ".join(seen):<36} -> {action}')
            done = done or (task if job == 'summarise Q3' else None)

        print('[2] a waiting call returns at a pause, not only at the end')
        t0 = time.time()
        task = await send(client, 'ask')            # default call: waits
        print(f'    returned after {time.time() - t0:.1f}s with state {name(task.status.state)}')

        print('[3] final means final: a message to the completed task')
        try:
            req = SendMessageRequest(message=new_text_message(
                'one more thing', role=Role.ROLE_USER, task_id=done.id, context_id=done.context_id))
            [r async for r in client.send_message(req)]
            print('    accepted (unexpected)')
        except Exception as e:
            print(f'    refused: {type(e).__name__}: {e}')
        await client.close()

# --- the remote agent (stand-in) ---
# The message text picks which path the task takes, so one run shows every state.
class Worker(AgentExecutor):
    async def execute(self, ctx, q):
        task = new_task_from_user_message(ctx.message); await q.enqueue_event(task)
        up, text = TaskUpdater(q, task.id, task.context_id), get_message_text(ctx.message)
        msg = lambda t: new_text_message(t, task_id=task.id, context_id=task.context_id)
        await asyncio.sleep(0.3); await up.start_work(); await asyncio.sleep(0.4)
        if text == 'ask':      return await up.requires_input(msg('Which quarter do you mean?'))
        if text == 'login':    return await up.requires_auth(msg('Needs a CRM access token.'))
        if text == 'break':    return await up.failed(msg('(CRM timed out)'))
        if text == 'refuse':   return await up.reject(msg('(not a job I do)'))
        if text == 'slow':     await asyncio.sleep(30)
        await up.add_artifact([new_text_part('Q3 revenue up 4%.')], name='summary')
        await up.complete()
    async def cancel(self, ctx, q):
        await TaskUpdater(q, ctx.task_id, ctx.context_id).cancel()

with socket.socket() as s:
    s.bind(('127.0.0.1', 0)); PORT = s.getsockname()[1]
URL = f'http://127.0.0.1:{PORT}'
card = AgentCard(name='Report Writer', description='Writes short reports.', version='1.0.0',
    default_input_modes=['text/plain'], default_output_modes=['text/plain'],
    capabilities=AgentCapabilities(streaming=False),
    supported_interfaces=[AgentInterface(protocol_binding='JSONRPC', url=URL, protocol_version='1.0')],
    skills=[AgentSkill(id='report', name='Write a report', description='Summarises data.', tags=['reports'])])
handler = DefaultRequestHandler(agent_executor=Worker(), task_store=InMemoryTaskStore(), agent_card=card)
app = Starlette(routes=[*create_agent_card_routes(card), *create_jsonrpc_routes(handler, '/')])
# a2a-sdk 1.3.0 logs a cleanup traceback on the server side after it refuses a message
# to a final task (a background task left pending). Hidden so the lab output stays readable.
logging.getLogger('opentelemetry.context').setLevel(logging.CRITICAL)
logging.getLogger('asyncio').setLevel(logging.CRITICAL)

# --- run both, then shut down ---
async def run():
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=PORT, log_level='warning'))
    serving = asyncio.create_task(server.serve())
    while not server.started: await asyncio.sleep(0.05)
    try: await main()
    finally:
        await handler.aclose(); server.should_exit = True; await serving

asyncio.run(run())
