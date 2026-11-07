"""Lab 19 (video section s19): cancelling, and follow-ups.

Cancel is a request: if the agent can stop, you get the task back, now CANCELED;
if it can't (the task already finished, say), you get an error. A finished task
can't be reopened: send a new message with the same context ID and list the
earlier task in referenceTaskIds; the agent answers with a new task (or just a
message) and can build on what came before. Run: python lab19_cancel_followup.py
"""
import asyncio, logging, socket
import httpx, uvicorn
from starlette.applications import Starlette
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import (get_artifact_text, get_message_text, new_message, new_task_from_user_message,
                         new_text_message, new_text_part)
from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution.simple_request_context_builder import SimpleRequestContextBuilder
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (AgentCapabilities, AgentCard, AgentInterface, AgentSkill, CancelTaskRequest,
                       GetTaskRequest, Role, SendMessageConfiguration, SendMessageRequest, TaskState)

# --- your agent: the client side ---
st = lambda t: TaskState.Name(t.status.state).removeprefix('TASK_STATE_')

async def send(client, msg, **config):
    req = SendMessageRequest(message=msg, configuration=SendMessageConfiguration(**config))
    return [r async for r in client.send_message(req)][-1].task

async def main():
    async with httpx.AsyncClient(timeout=10) as http:
        card = await A2ACardResolver(http, URL).get_agent_card()
        client = await create_client(card, client_config=ClientConfig(httpx_client=http, streaming=False))
        user = lambda text, **ids: new_text_message(text, role=Role.ROLE_USER, **ids)

        print('[1] cancel a running task')
        task = await send(client, user('Translate the full archive'), return_immediately=True)
        while st(task) != 'WORKING':
            await asyncio.sleep(0.1); task = await client.get_task(GetTaskRequest(id=task.id))
        print(f'    before: {st(task)}')
        task = await client.cancel_task(CancelTaskRequest(id=task.id))
        print(f'    cancel returned the task, now {st(task)}')

        print('[2] cancel a task that already finished')
        first = await send(client, user('Write a tagline for our bakery'))
        print(f'    task {first.id[:8]}.. {st(first)}: "{get_artifact_text(first.artifacts[0])}"')
        try:
            await client.cancel_task(CancelTaskRequest(id=first.id))
        except Exception as e:
            print(f'    error: {type(e).__name__}: {e}')

        print("[3] a finished task can't be reopened")
        try:
            await send(client, user('Make it shorter', task_id=first.id, context_id=first.context_id))
        except Exception as e:
            print(f'    error: {type(e).__name__}: {e}'.replace(first.id, first.id[:8] + '..'))

        print('[4] follow-up: same contextId, referenceTaskIds -> a new task')
        # The agent created this context ID; treat it as opaque and reuse it as given.
        follow = new_message([new_text_part('Make it shorter')], role=Role.ROLE_USER, context_id=first.context_id)
        follow.reference_task_ids.append(first.id)
        second = await send(client, follow)
        print(f'    new task {second.id[:8]}.. {st(second)}  new id: {second.id != first.id}  '
              f'same context: {second.context_id == first.context_id}')
        print(f'    "{get_artifact_text(second.artifacts[0])}"')
        await client.close()

# --- the remote agent (stand-in) ---
# "Translate" runs until cancelled. A message that references an earlier task
# builds on that task's artifact, which the SDK hands it as related_tasks.
class Writer(AgentExecutor):
    async def execute(self, ctx, q):
        task = new_task_from_user_message(ctx.message); await q.enqueue_event(task)
        up = TaskUpdater(q, task.id, task.context_id)
        await asyncio.sleep(0.2); await up.start_work()
        text = get_message_text(ctx.message)
        if text.startswith('Translate'):
            await asyncio.sleep(30)
        if ctx.related_tasks:
            earlier = get_artifact_text(ctx.related_tasks[0].artifacts[0])
            result = f'{earlier.split(",")[0]}. (shorter version of task {ctx.related_tasks[0].id[:8]}..)'
        else:
            result = 'Warm bread, baked fresh every morning.'
        await up.add_artifact([new_text_part(result)], name='tagline')
        await up.complete()
    async def cancel(self, ctx, q):
        await TaskUpdater(q, ctx.task_id, ctx.context_id).cancel()

with socket.socket() as s:
    s.bind(('127.0.0.1', 0)); PORT = s.getsockname()[1]
URL = f'http://127.0.0.1:{PORT}'
card = AgentCard(name='Copy Writer', description='Writes short marketing copy.', version='1.0.0',
    default_input_modes=['text/plain'], default_output_modes=['text/plain'],
    capabilities=AgentCapabilities(streaming=False),
    supported_interfaces=[AgentInterface(protocol_binding='JSONRPC', url=URL, protocol_version='1.0')],
    skills=[AgentSkill(id='copy', name='Write copy', description='Writes taglines.', tags=['marketing'])])
store = InMemoryTaskStore()
handler = DefaultRequestHandler(agent_executor=Writer(), task_store=store, agent_card=card,
    # look up tasks named in referenceTaskIds and pass them to the executor
    request_context_builder=SimpleRequestContextBuilder(should_populate_referred_tasks=True, task_store=store))
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
