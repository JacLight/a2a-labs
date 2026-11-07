"""Lab 08 (video section s08): handling a job.

You write an agent executor with two methods: execute (incoming messages) and
cancel. The SDK's request handler calls them and keeps tasks in a task store.
execute: get or create the task -> WORKING with a status message -> run your
agent -> add its result as an artifact -> COMPLETED. A streaming caller sees
each step; a non-streaming caller gets the final task. A quick answer can be a
single Message, and then no task is created.
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
from a2a.types import (AgentCapabilities, AgentCard, AgentInterface, AgentSkill, ListTasksRequest, Role,
                       SendMessageRequest, TaskState)

with socket.socket() as s:
    s.bind(('127.0.0.1', 0)); PORT = s.getsockname()[1]
URL = f'http://127.0.0.1:{PORT}'


class HelloAgent:                                 # stands in for an agent you already have
    async def invoke(self, user_request: str) -> str:   # (LangGraph, CrewAI, your own code...)
        return f'Hello, World! I have received your request ({user_request})'


class HelloExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        query = get_message_text(context.message)
        if query == 'ping':                       # quick answer, nothing to track: reply with a Message
            await event_queue.enqueue_event(new_text_message('pong', role=Role.ROLE_AGENT))
            return
        task = context.current_task               # the task, if this message continues one
        if not task:                              # no task yet: create one
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue=event_queue, task_id=task.id, context_id=task.context_id)
        await updater.update_status(state=TaskState.TASK_STATE_WORKING,
                                    message=new_text_message('Processing request...'))
        result = await HelloAgent().invoke(user_request=query)          # run your agent
        await updater.add_artifact(parts=[new_text_part(text=result, media_type='text/plain')])
        await updater.update_status(state=TaskState.TASK_STATE_COMPLETED,
                                    message=new_text_message('Request is completed!'))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError('Cancel is not supported.')         # lab 09 covers cancel


card = AgentCard(
    name='Hello World Agent', description='Just a hello world agent', version='0.0.1',
    default_input_modes=['text/plain'], default_output_modes=['text/plain'],
    capabilities=AgentCapabilities(streaming=True),
    supported_interfaces=[AgentInterface(protocol_binding='JSONRPC', url=URL, protocol_version='1.0')],
    skills=[AgentSkill(id='echo_bot', name='Echo Bot', description='Replies with a hello.',
                       tags=['echo'], examples=['hi'])])
handler = DefaultRequestHandler(agent_executor=HelloExecutor(), task_store=InMemoryTaskStore(),
                                agent_card=card)
app = Starlette(routes=[*create_agent_card_routes(card), *create_jsonrpc_routes(handler, '/')])


def describe(event) -> str:                       # one line per thing the caller receives
    kind = event.WhichOneof('payload')
    if kind == 'task':
        t = event.task
        line = f'task          {TaskState.Name(t.status.state)}'
        return line + (f'  artifact: "{get_artifact_text(t.artifacts[0])}"' if t.artifacts else '')
    if kind == 'status_update':
        st = event.status_update.status
        return f'status_update {TaskState.Name(st.state)}  "{get_message_text(st.message)}"'
    if kind == 'artifact_update':
        return f'artifact_update "{get_artifact_text(event.artifact_update.artifact)}"'
    return f'message       "{get_message_text(event.message)}"  (no task created)'


async def send(text: str, streaming: bool):
    client = await create_client(card, client_config=ClientConfig(streaming=streaming))
    request = SendMessageRequest(message=new_text_message(text, role=Role.ROLE_USER))
    async for event in client.send_message(request):
        print('    ' + describe(event))
    await client.close()


async def main():
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=PORT, log_level='warning'))
    serving = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)
    print('[1] streaming caller sends "hi": every step, in order')
    await send('hi', streaming=True)
    print('[2] non-streaming caller sends "hi": one final task')
    await send('hi', streaming=False)
    print('[3] caller sends "ping": the agent answers with a single Message')
    await send('ping', streaming=False)
    client = await create_client(card)
    tasks = (await client.list_tasks(ListTasksRequest())).tasks
    print(f'[4] tasks in the store: {len(tasks)} (the two "hi" jobs; "ping" made none)')
    await client.close()
    server.should_exit = True
    await serving


asyncio.run(main())
