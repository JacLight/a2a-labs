"""Lab 16 (video section s16): getting the results.

When a task completes, its artifacts are the output (text, files or data). The
agent's messages are progress and questions, and the agent decides which it keeps
in the task's history. GetTask takes a task ID and how much recent history you
want; ListTasks finds tasks you started, filtered by conversation or state,
newest first. Run: python lab16_results.py
"""
import asyncio, socket
import httpx, uvicorn
from starlette.applications import Starlette
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import (get_message_text, new_data_part, new_task_from_user_message, new_text_message,
                         new_text_part, new_url_part)
from a2a.server.agent_execution import AgentExecutor
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (AgentCapabilities, AgentCard, AgentInterface, AgentSkill, GetTaskRequest,
                       ListTasksRequest, Role, SendMessageRequest, TaskState)

# --- your agent: the client side ---
st = lambda t: TaskState.Name(t.status.state).removeprefix('TASK_STATE_')

async def send(client, text, context_id=None):
    msg = new_text_message(text, role=Role.ROLE_USER, context_id=context_id)
    return [r async for r in client.send_message(SendMessageRequest(message=msg))][-1].task

async def main():
    async with httpx.AsyncClient(timeout=10) as http:
        card = await A2ACardResolver(http, URL).get_agent_card()
        client = await create_client(card, client_config=ClientConfig(httpx_client=http, streaming=False))

        print('[1] collect the artifacts of a completed task')
        a = await send(client, 'find faces in team.png')
        for art in a.artifacts:
            kinds = [p.WhichOneof('content') for p in art.parts]
            print(f'    {art.name}: {kinds} {art.parts[0].media_type}')

        print('[2] GetTask with historyLength (a maximum; the agent may keep or send fewer)')
        for n in (None, 1, 0):
            req = GetTaskRequest(id=a.id) if n is None else GetTaskRequest(id=a.id, history_length=n)
            t = await client.get_task(req)
            print(f'    historyLength={"not set" if n is None else n}: {len(t.history)} message(s)',
                  [get_message_text(m)[:20] for m in t.history])
        print(f'    current status message (not in history): "{get_message_text(t.status.message)}"')

        print('[3] ListTasks, filtered (newest first)')
        b = await send(client, 'now find faces in team2.png', context_id=a.context_id)  # same conversation
        c = await send(client, 'find faces')                                            # new one; pauses
        label = {a.id: 'a', b.id: 'b', c.id: 'c'}
        mine = await client.list_tasks(ListTasksRequest(context_id=a.context_id))
        print(f'    contextId of a: {[(label[t.id], st(t)) for t in mine.tasks]}  total={mine.total_size}')
        paused = await client.list_tasks(ListTasksRequest(status=TaskState.TASK_STATE_INPUT_REQUIRED))
        print(f'    status INPUT_REQUIRED: {[(label[t.id], st(t)) for t in paused.tasks]}')
        everything = await client.list_tasks(ListTasksRequest(page_size=2, include_artifacts=False))
        print(f'    page_size=2: {[label[t.id] for t in everything.tasks]}  '
              f'next page token: {"yes" if everything.next_page_token else "no"}  '
              f'artifacts included: {any(t.artifacts for t in everything.tasks)}')
        await client.close()

# --- the remote agent (stand-in) ---
# A message naming an image completes with three artifacts; one without pauses
# with a question. Progress messages go in the task status as it works.
class FaceFinder(AgentExecutor):
    async def execute(self, ctx, q):
        task = new_task_from_user_message(ctx.message); await q.enqueue_event(task)
        up = TaskUpdater(q, task.id, task.context_id)
        say = lambda t: new_text_message(t, task_id=task.id, context_id=task.context_id)
        if '.png' not in get_message_text(ctx.message):
            return await up.requires_input(say('Which image should I look at?'))
        await up.start_work(say('Loading the image...'))
        await up.start_work(say('Found 2 faces, drawing boxes...'))
        await up.add_artifact([new_url_part('https://example.com/output.png', media_type='image/png',
                                            filename='processed_image_with_faces.png')], name='image')
        await up.add_artifact([new_data_part({'faces': 2}, media_type='application/json')], name='counts')
        await up.add_artifact([new_text_part('Two faces, both smiling.', media_type='text/plain')], name='note')
        await up.complete(say('Done.'))
    async def cancel(self, ctx, q): pass

with socket.socket() as s:
    s.bind(('127.0.0.1', 0)); PORT = s.getsockname()[1]
URL = f'http://127.0.0.1:{PORT}'
card = AgentCard(name='Face Finder', description='Finds faces in images.', version='1.0.0',
    default_input_modes=['text/plain'], default_output_modes=['image/png', 'application/json', 'text/plain'],
    capabilities=AgentCapabilities(streaming=False),
    supported_interfaces=[AgentInterface(protocol_binding='JSONRPC', url=URL, protocol_version='1.0')],
    skills=[AgentSkill(id='faces', name='Find faces', description='Finds faces in an image.', tags=['vision'])])
handler = DefaultRequestHandler(agent_executor=FaceFinder(), task_store=InMemoryTaskStore(), agent_card=card)
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
