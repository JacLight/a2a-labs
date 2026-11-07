"""Lab 06 (video section s06): the smallest A2A server.

Two things make your agent available: an Agent Card, and an A2A server that
receives jobs, runs them with your agent and reports back. The SDK does the
protocol; you write the executor: what happens when a job arrives.
Adapted from the official A2A Hello World sample (a2a-sdk 1.3.0).
"""
import asyncio, socket
import uvicorn
from starlette.applications import Starlette
from a2a.client import ClientConfig, create_client
from a2a.helpers import (get_artifact_text, get_message_text, new_task_from_user_message,
                         new_text_message, new_text_part)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (AgentCapabilities, AgentCard, AgentInterface, AgentSkill, Role,
                       SendMessageRequest, TaskState)

with socket.socket() as s:                       # pick a free port on this machine
    s.bind(('127.0.0.1', 0)); PORT = s.getsockname()[1]
URL = f'http://127.0.0.1:{PORT}'


class HelloAgent:                                # "your agent": any code, any framework, or none
    async def invoke(self, text: str) -> str:
        return f'Hello, World! I have received your request ({text})'


class HelloExecutor(AgentExecutor):              # your code: the bridge between A2A and your agent
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task or new_task_from_user_message(context.message)
        if not context.current_task:
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue=event_queue, task_id=task.id, context_id=task.context_id)
        result = await HelloAgent().invoke(get_message_text(context.message))
        await updater.add_artifact(parts=[new_text_part(text=result, media_type='text/plain')])
        await updater.update_status(state=TaskState.TASK_STATE_COMPLETED)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError('Cancel is not supported.')   # same choice as the sample


# Part 1: the Agent Card (who you are, what you do, where to reach you).
card = AgentCard(
    name='Hello World Agent', description='Just a hello world agent', version='0.0.1',
    default_input_modes=['text/plain'], default_output_modes=['text/plain'],
    capabilities=AgentCapabilities(streaming=False),
    supported_interfaces=[AgentInterface(protocol_binding='JSONRPC', url=URL, protocol_version='1.0')],
    skills=[AgentSkill(id='echo_bot', name='Echo Bot', description='Replies with a hello.',
                       tags=['echo'], examples=['hi', 'how are you'])])

# Part 2: the A2A server. The SDK's request handler runs your executor and keeps tasks in a store.
handler = DefaultRequestHandler(agent_executor=HelloExecutor(), task_store=InMemoryTaskStore(),
                                agent_card=card)
app = Starlette(routes=[*create_agent_card_routes(card), *create_jsonrpc_routes(handler, '/')])


async def main():
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=PORT, log_level='warning'))
    serving = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)
    print(f'[1] server up at {URL}')
    print(f'    card:     {URL}/.well-known/agent-card.json')
    print(f'    JSON-RPC: {URL}/')

    # A caller: read the card from the URL, then send one message.
    client = await create_client(URL, client_config=ClientConfig(streaming=False))
    print('[2] send "hi"')
    request = SendMessageRequest(message=new_text_message('hi', role=Role.ROLE_USER))
    async for response in client.send_message(request):
        task = response.task
        print(f'[3] reply: task {task.id[:8]}...  state {TaskState.Name(task.status.state)}')
        print(f'    artifact: {get_artifact_text(task.artifacts[0])}')
    await client.close()

    server.should_exit = True
    await serving
    print('[4] server stopped')


asyncio.run(main())
