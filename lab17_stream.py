"""Lab 17 (video section s17): live updates with streaming.

Check the card supports streaming, then send with streaming on (one setting on the
Python SDK's client). The stream starts with the task, then brings a status update
when the state changes and an artifact update when output is ready. A large output
can arrive in pieces (append, last chunk). If the connection drops, subscribe to
the task again: first you get the task as it is now, then the updates continue.
Run: python lab17_stream.py
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
from a2a.types import (AgentCapabilities, AgentCard, AgentInterface, AgentSkill, Role,
                       SendMessageRequest, SubscribeToTaskRequest, TaskState)

# --- your agent: the client side ---
st = lambda s: TaskState.Name(s).removeprefix('TASK_STATE_')
pieces = {}                                   # artifact_id -> text assembled so far

def show(ev):
    kind = ev.WhichOneof('payload')
    if kind == 'task':
        t = ev.task
        for a in t.artifacts: pieces[a.artifact_id] = ''.join(p.text for p in a.parts)
        return f'task           {st(t.status.state)}' + (f'  (artifact so far: "{"".join(pieces.values())}")' if t.artifacts else '')
    if kind == 'status_update':
        s = ev.status_update.status
        return f'status update  {st(s.state)}' + (f' "{get_message_text(s.message)}"' if s.HasField('message') else '')
    u = ev.artifact_update
    text = ''.join(p.text for p in u.artifact.parts)
    pieces[u.artifact.artifact_id] = (pieces.get(u.artifact.artifact_id, '') if u.append else '') + text
    return f'artifact update "{text}"  append={u.append} last_chunk={u.last_chunk}'

def job(text):
    return SendMessageRequest(message=new_text_message(text, role=Role.ROLE_USER))

async def main():
    async with httpx.AsyncClient(timeout=10) as http:
        card = await A2ACardResolver(http, URL).get_agent_card()
        print(f'[1] card says streaming: {card.capabilities.streaming}')
        client = await create_client(card, client_config=ClientConfig(httpx_client=http, streaming=True))

        print('[2] stream a job; each update in order')
        async for ev in client.send_message(job('Hi there')):
            print('   ', show(ev))
        print(f'    stream closed; assembled artifact: "{"".join(pieces.values())}"')

        print('[3] drop the stream part-way, then subscribe to the task again')
        pieces.clear()
        stream = client.send_message(job('Hi again'))
        async for ev in stream:
            print('   ', show(ev))
            if ev.WhichOneof('payload') == 'artifact_update':
                task_id = ev.artifact_update.task_id; break      # connection "drops" here
        await stream.aclose()
        await asyncio.sleep(0.6)                                 # updates go on without us
        async for ev in client.subscribe(SubscribeToTaskRequest(id=task_id)):
            print('    (resubscribed)', show(ev))
        print(f'    assembled artifact: "{"".join(pieces.values())}"')
        await client.close()

# --- the remote agent (stand-in) ---
# Like the official Hello World sample, but the greeting arrives in three pieces.
class HelloAgent(AgentExecutor):
    async def execute(self, ctx, q):
        task = new_task_from_user_message(ctx.message); await q.enqueue_event(task)
        up = TaskUpdater(q, task.id, task.context_id)
        await up.start_work(new_text_message('Processing request...', task_id=task.id, context_id=task.context_id))
        chunks = ['Hello, ', 'World! ', f'({get_message_text(ctx.message)})']
        for i, chunk in enumerate(chunks):
            await asyncio.sleep(0.4)
            await up.add_artifact([new_text_part(chunk)], artifact_id='greeting', name='greeting',
                                  append=i > 0, last_chunk=i == len(chunks) - 1)
        await up.complete()
    async def cancel(self, ctx, q): pass

with socket.socket() as s:
    s.bind(('127.0.0.1', 0)); PORT = s.getsockname()[1]
URL = f'http://127.0.0.1:{PORT}'
card = AgentCard(name='Hello World Agent', description='Just a hello world agent', version='0.0.1',
    default_input_modes=['text/plain'], default_output_modes=['text/plain'],
    capabilities=AgentCapabilities(streaming=True),
    supported_interfaces=[AgentInterface(protocol_binding='JSONRPC', url=URL, protocol_version='1.0')],
    skills=[AgentSkill(id='echo_bot', name='Echo Bot', description='Says hello.', tags=['echo-example'])])
handler = DefaultRequestHandler(agent_executor=HelloAgent(), task_store=InMemoryTaskStore(), agent_card=card)
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
