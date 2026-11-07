"""Lab 15 (video section s15): when it needs a login or an approval.

The remote task goes AUTH_REQUIRED, and its status message says what it needs.
The credential normally doesn't travel inside an A2A message: it reaches the agent
by a separate route (here, a stand-in for an OAuth sign-in). Once it arrives, the
agent may carry on without any message from you, so you keep listening; this lab
subscribes to the task (keeping a stream open, push notifications, or checking the
task are the other ways). Run: python lab15_auth_required.py
"""
import asyncio, socket
import httpx, uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
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

def describe(ev):
    kind = ev.WhichOneof('payload')
    if kind == 'task': return f'task snapshot, {st(ev.task.status.state)}'
    if kind == 'status_update': return f'status update, {st(ev.status_update.status.state)}'
    return f'artifact update, "{ev.artifact_update.artifact.parts[0].text}"'

async def main():
    async with httpx.AsyncClient(timeout=10) as http:
        card = await A2ACardResolver(http, URL).get_agent_card()
        client = await create_client(card, client_config=ClientConfig(httpx_client=http, streaming=False))
        streamer = await create_client(card, client_config=ClientConfig(httpx_client=http, streaming=True))

        print('[1] send the job; the waiting call returns at the pause')
        msg = new_text_message("What's on my calendar tomorrow?", role=Role.ROLE_USER)
        task = [r async for r in client.send_message(SendMessageRequest(message=msg))][-1].task
        print(f'    {st(task.status.state)}: "{get_message_text(task.status.message)}"')

        print('[2] keep listening: subscribe to the task')
        snapshot = asyncio.Event()
        async def listen():
            async for ev in streamer.subscribe(SubscribeToTaskRequest(id=task.id)):
                print('    stream:', describe(ev)); snapshot.set()
        listening = asyncio.create_task(listen())
        await snapshot.wait()

        # [3] STAND-IN for an OAuth sign-in. In real life a person signs in with the
        #     provider, which sends the agent the credential over its own HTTPS route.
        #     Here one plain POST plays that part. It is not an A2A message, and your
        #     A2A client never sends the token to the agent.
        print('[3] out of band: the sign-in delivers a token to the agent (stand-in)')
        r = await http.post(f'{URL}/oauth/callback', json={'task_id': task.id, 'access_token': 'demo-token-123'})
        print(f'    sign-in route answered {r.status_code}; no A2A message sent')

        print('[4] the task carries on by itself; updates arrive on the stream')
        await listening                          # the stream closes when the task finishes
        await client.close(); await streamer.close()

# --- the remote agent (stand-in) ---
# It needs a calendar token. It waits for the token on its own sign-in route, then
# checks for itself what the token allows: the AUTH_REQUIRED state grants nothing.
ISSUED = {'demo-token-123': {'calendar.read'}}     # stand-in for the token issuer's records
arrived: dict[str, asyncio.Future] = {}

class CalendarAgent(AgentExecutor):
    async def execute(self, ctx, q):
        task = new_task_from_user_message(ctx.message); await q.enqueue_event(task)
        up = TaskUpdater(q, task.id, task.context_id)
        await up.start_work()
        arrived[task.id] = asyncio.get_running_loop().create_future()
        await up.requires_auth(new_text_message(
            'Needs an OAuth access token for the Calendar API (scope calendar.read).',
            task_id=task.id, context_id=task.context_id))
        token = await arrived[task.id]                 # comes in on /oauth/callback
        await asyncio.sleep(0.3)
        if 'calendar.read' not in ISSUED.get(token, set()):
            return await up.failed(new_text_message('Token does not allow calendar.read.'))
        await up.start_work()
        await up.add_artifact([new_text_part('09:00 stand-up; 14:00 dentist')], name='agenda')
        await up.complete()
    async def cancel(self, ctx, q): pass

async def oauth_callback(request):                     # the separate route, outside A2A
    body = await request.json()
    arrived[body['task_id']].set_result(body['access_token'])
    return JSONResponse({'ok': True})

with socket.socket() as s:
    s.bind(('127.0.0.1', 0)); PORT = s.getsockname()[1]
URL = f'http://127.0.0.1:{PORT}'
card = AgentCard(name='Calendar Agent', description='Answers questions about your calendar.', version='1.0.0',
    default_input_modes=['text/plain'], default_output_modes=['text/plain'],
    capabilities=AgentCapabilities(streaming=True),
    supported_interfaces=[AgentInterface(protocol_binding='JSONRPC', url=URL, protocol_version='1.0')],
    skills=[AgentSkill(id='agenda', name='Read the agenda', description='Reads your calendar.', tags=['calendar'])])
handler = DefaultRequestHandler(agent_executor=CalendarAgent(), task_store=InMemoryTaskStore(), agent_card=card)
app = Starlette(routes=[*create_agent_card_routes(card), *create_jsonrpc_routes(handler, '/'),
                        Route('/oauth/callback', oauth_callback, methods=['POST'])])

# --- run both, then shut down ---
async def run():
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=PORT, log_level='warning'))
    serving = asyncio.create_task(server.serve())
    while not server.started: await asyncio.sleep(0.05)
    try: await main()
    finally:
        await handler.aclose(); server.should_exit = True; await serving

asyncio.run(run())
