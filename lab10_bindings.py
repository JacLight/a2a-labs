"""Lab 10 (video section s10): serving your agent over more than one binding.

A binding is the concrete format the A2A calls are sent in: JSON-RPC, gRPC or
HTTP+JSON. You can offer one or several; each must behave the same. You list
them in the card's supported interfaces, preferred first, and a caller uses the
first one on that list it supports. Here one agent is served over JSON-RPC and
HTTP+JSON. (The SDK's gRPC handler needs the grpcio package, so it is left out.)
The SDK's routes plug into an ordinary Starlette app, so the logging below is ours.
"""
import asyncio, socket
import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from a2a.client import ClientConfig, create_client
from a2a.helpers import (get_artifact_text, get_message_text, new_task_from_user_message,
                         new_text_message, new_text_part)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes, create_rest_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (AgentCapabilities, AgentCard, AgentInterface, AgentSkill, Role,
                       SendMessageRequest, TaskState)

with socket.socket() as s:
    s.bind(('127.0.0.1', 0)); PORT = s.getsockname()[1]
URL = f'http://127.0.0.1:{PORT}'


class HelloExecutor(AgentExecutor):              # the same executor serves every binding
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task or new_task_from_user_message(context.message)
        if not context.current_task:
            await event_queue.enqueue_event(task)
        up = TaskUpdater(event_queue=event_queue, task_id=task.id, context_id=task.context_id)
        await up.add_artifact(parts=[new_text_part(f'Hello! ({get_message_text(context.message)})')])
        await up.update_status(state=TaskState.TASK_STATE_COMPLETED)

    async def cancel(self, context, event_queue):
        raise NotImplementedError('Cancel is not supported.')


card = AgentCard(
    name='Hello World Agent', description='Just a hello world agent', version='0.0.1',
    default_input_modes=['text/plain'], default_output_modes=['text/plain'],
    capabilities=AgentCapabilities(streaming=False),
    supported_interfaces=[                       # ordered: the first entry is the preferred one
        AgentInterface(protocol_binding='JSONRPC', url=f'{URL}/jsonrpc', protocol_version='1.0'),
        AgentInterface(protocol_binding='HTTP+JSON', url=f'{URL}/rest', protocol_version='1.0')],
    skills=[AgentSkill(id='echo_bot', name='Echo Bot', description='Replies with a hello.',
                       tags=['echo'], examples=['hi'])])
handler = DefaultRequestHandler(agent_executor=HelloExecutor(), task_store=InMemoryTaskStore(),
                                agent_card=card)


async def log_requests(request, call_next):      # our own logging: which route did each call hit?
    print(f'    server saw: {request.method} {request.url.path}')
    return await call_next(request)

app = Starlette(
    routes=[*create_agent_card_routes(card),
            *create_jsonrpc_routes(handler, '/jsonrpc'),             # JSON-RPC binding
            *create_rest_routes(handler, path_prefix='/rest')],     # HTTP+JSON (REST) binding
    middleware=[Middleware(BaseHTTPMiddleware, dispatch=log_requests)])


async def caller(label: str, supports: list[str]):
    print(f'[{label}] caller supports {supports}')
    client = await create_client(card, client_config=ClientConfig(
        streaming=False, supported_protocol_bindings=supports))
    request = SendMessageRequest(message=new_text_message('hi', role=Role.ROLE_USER))
    async for event in client.send_message(request):
        task = event.task
        print(f'    reply: {TaskState.Name(task.status.state)}  "{get_artifact_text(task.artifacts[0])}"')
    await client.close()


async def main():
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=PORT, log_level='warning'))
    serving = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)
    print('[card] supported interfaces, in order:')
    for i, iface in enumerate(card.supported_interfaces, 1):
        print(f'    {i}. {iface.protocol_binding:<10} {iface.url}')
    await caller('A', ['HTTP+JSON', 'JSONRPC'])  # supports both: the card's order decides, so JSON-RPC
    await caller('B', ['HTTP+JSON'])             # supports only HTTP+JSON: takes that one
    await caller('C', ['JSONRPC'])               # supports only JSON-RPC
    server.should_exit = True
    await serving


asyncio.run(main())
