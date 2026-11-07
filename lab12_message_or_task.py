"""Lab 12 (video section s12): sending the job.

A message is made of parts (text, a file as bytes or a link, structured data).
What comes back is either a Message or a Task; the remote agent decides, so the
client handles both. The default call waits; returnImmediately gets the task back
at once. acceptedOutputModes lists the media types you accept.
Run: python lab12_message_or_task.py
"""
import asyncio, socket, time
import httpx, uvicorn
from starlette.applications import Starlette
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import (new_data_part, new_message, new_raw_part, new_task_from_user_message,
                         new_text_message, new_text_part)
from a2a.server.agent_execution import AgentExecutor
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (AgentCapabilities, AgentCard, AgentInterface, AgentSkill, GetTaskRequest,
                       Role, SendMessageConfiguration, SendMessageRequest, TaskState)

# --- your agent: the client side ---
FINAL = {TaskState.TASK_STATE_COMPLETED, TaskState.TASK_STATE_FAILED,
         TaskState.TASK_STATE_CANCELED, TaskState.TASK_STATE_REJECTED}
PAUSED = {TaskState.TASK_STATE_INPUT_REQUIRED, TaskState.TASK_STATE_AUTH_REQUIRED}
st = TaskState.Name

def show(reply):
    """The answer is a Message (nothing to track) or a Task (track it by id)."""
    if reply.HasField('message'):
        return f'Message: "{reply.message.parts[0].text}"'
    t = reply.task
    return f'Task id={t.id[:8]}.. contextId={t.context_id[:8]}.. state={st(t.status.state)}'

async def send(client, msg, **config):
    req = SendMessageRequest(message=msg, configuration=SendMessageConfiguration(**config))
    return [r async for r in client.send_message(req)][-1]   # non-streaming: one reply

async def main():
    async with httpx.AsyncClient(timeout=10) as http:
        card = await A2ACardResolver(http, URL).get_agent_card()
        client = await create_client(card, client_config=ClientConfig(httpx_client=http, streaming=False))

        print('[1] a quick question, nothing to track')
        print('   ', show(await send(client, new_text_message('Are you open today?', role=Role.ROLE_USER))))

        # One message, three parts: the request, the image it's about, and some data.
        job = lambda: new_message(role=Role.ROLE_USER, parts=[
            new_text_part('Analyze this image and highlight any faces.'),
            new_raw_part(b'\x89PNG\r\n\x1a\n...', media_type='image/png', filename='input_image.png'),
            new_data_part({'max_faces': 5})])
        print('[2] a job: parts =', [p.WhichOneof('content') for p in job().parts])

        print('[3] default call: waits until the task finishes (or pauses)')
        t0 = time.time()
        reply = await send(client, job(), accepted_output_modes=['application/json'])
        print(f'    after {time.time() - t0:.1f}s:', show(reply))
        print('    accepted application/json -> artifact part:', reply.task.artifacts[0].parts[0].WhichOneof('content'))

        print('[4] returnImmediately: the task comes back as soon as it exists')
        t0 = time.time()
        reply = await send(client, job(), return_immediately=True, accepted_output_modes=['text/plain'])
        print(f'    after {time.time() - t0:.1f}s:', show(reply))
        task, seen = reply.task, []
        while task.status.state not in FINAL | PAUSED:    # follow it: here, by checking
            seen.append(st(task.status.state))
            await asyncio.sleep(0.3)
            task = await client.get_task(GetTaskRequest(id=task.id))
        print('    states seen while checking:', ' -> '.join(dict.fromkeys(seen + [st(task.status.state)])))
        print('    accepted text/plain -> artifact part:', task.artifacts[0].parts[0].WhichOneof('content'),
              f'"{task.artifacts[0].parts[0].text}"')
        await client.close()

# --- the remote agent (stand-in) ---
# Its choice: a message with no file gets a direct Message; a message with a file
# becomes a Task. It shapes its result to the caller's accepted output modes.
class Analyzer(AgentExecutor):
    async def execute(self, ctx, q):
        if not any(p.raw for p in ctx.message.parts):
            await q.enqueue_event(new_text_message('Yes, until 18:00.', context_id=ctx.context_id))
            return
        task = new_task_from_user_message(ctx.message)   # state: SUBMITTED
        await q.enqueue_event(task)
        up = TaskUpdater(q, task.id, task.context_id)
        await asyncio.sleep(0.4); await up.start_work()
        await asyncio.sleep(0.8)
        modes = list(ctx.configuration.accepted_output_modes) if ctx.configuration else []
        if 'application/json' in modes or not modes:
            part = new_data_part({'faces': 2}, media_type='application/json')
        else:
            part = new_text_part('2 faces found.', media_type='text/plain')
        await up.add_artifact([part], name='faces')
        await up.complete()
    async def cancel(self, ctx, q): pass

with socket.socket() as s:
    s.bind(('127.0.0.1', 0)); PORT = s.getsockname()[1]
URL = f'http://127.0.0.1:{PORT}'
card = AgentCard(name='Image Analyzer', description='Finds faces in images.', version='1.0.0',
    default_input_modes=['text/plain', 'image/png'], default_output_modes=['application/json', 'text/plain'],
    capabilities=AgentCapabilities(streaming=False),
    supported_interfaces=[AgentInterface(protocol_binding='JSONRPC', url=URL, protocol_version='1.0')],
    skills=[AgentSkill(id='faces', name='Find faces', description='Finds faces in an image.', tags=['vision'])])
handler = DefaultRequestHandler(agent_executor=Analyzer(), task_store=InMemoryTaskStore(), agent_card=card)
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
