"""Lab 09 (video section s09): stopping to ask, and cancels.

If your agent needs more from the caller, set the task to INPUT_REQUIRED and
put the question in the status message. The answer arrives as a new message on
the same task, and execute runs again with that task.
When a caller cancels, the SDK calls your cancel method. There you can try to
stop the work and set CANCELED, or refuse (as the official samples do).
"""
import asyncio, logging, socket
import uvicorn
from starlette.applications import Starlette
from a2a.client import ClientConfig, create_client
from a2a.helpers import (get_artifact_text, get_message_text, new_task_from_user_message,
                         new_text_message, new_text_part)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (AgentCapabilities, AgentCard, AgentInterface, AgentSkill, CancelTaskRequest,
                       GetTaskRequest, Role, SendMessageRequest, TaskState)
from a2a.utils.errors import UnsupportedOperationError

with socket.socket() as s:
    s.bind(('127.0.0.1', 0)); PORT = s.getsockname()[1]
URL = f'http://127.0.0.1:{PORT}'
logging.getLogger('a2a').setLevel(logging.CRITICAL)   # the SDK logs a refused cancel with a full traceback


class Converter(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        text = get_message_text(context.message)
        task = context.current_task
        if not task:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)
        up = TaskUpdater(event_queue=event_queue, task_id=task.id, context_id=task.context_id)
        await up.update_status(state=TaskState.TASK_STATE_WORKING)
        if text == 'Convert every price list':        # a long job (used for the cancel demo)
            await asyncio.sleep(60)
        elif text == 'Convert 100 USD':               # target currency missing: stop and ask
            await up.update_status(state=TaskState.TASK_STATE_INPUT_REQUIRED, message=new_text_message(
                'To which currency would you like to convert?', task_id=task.id, context_id=task.context_id))
        else:                                         # the answer, on the same task
            await up.add_artifact(parts=[new_text_part(f'100 USD = 92 {text} (example rate)')])
            await up.update_status(state=TaskState.TASK_STATE_COMPLETED)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        # Way 1: try to stop the work, then set the task to CANCELED.
        # (The SDK also stops the running execute call after this method returns.)
        up = TaskUpdater(event_queue=event_queue, task_id=context.task_id, context_id=context.context_id)
        await up.update_status(state=TaskState.TASK_STATE_CANCELED)


class RefusingConverter(Converter):
    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        # Way 2: refuse. In a2a-sdk 1.3.0 the LangGraph sample's ServerError(error=UnsupportedOperationError())
        # is written as a plain raise. What 1.3.0 then does (see step [4] output): it answers the caller
        # with TaskNotCancelableError and marks the task FAILED. That is this SDK's choice, not a spec rule.
        raise UnsupportedOperationError()


def card_for(path):
    return AgentCard(name='Currency Agent', description='Converts amounts.', version='1.0.0',
                     default_input_modes=['text/plain'], default_output_modes=['text/plain'],
                     capabilities=AgentCapabilities(streaming=False),
                     skills=[AgentSkill(id='convert', name='Convert currency', tags=['currency'],
                                        description='Converts an amount.', examples=['Convert 100 USD'])],
                     supported_interfaces=[AgentInterface(protocol_binding='JSONRPC', url=URL + path,
                                                          protocol_version='1.0')])


def routes(executor, path):                     # one app, two copies of the agent: one per cancel choice
    h = DefaultRequestHandler(agent_executor=executor, task_store=InMemoryTaskStore(), agent_card=card_for(path))
    return create_jsonrpc_routes(h, path)


app = Starlette(routes=[*routes(Converter(), '/stops'), *routes(RefusingConverter(), '/refuses')])
state = TaskState.Name


async def send(client, text, task=None):
    msg = new_text_message(text, role=Role.ROLE_USER, task_id=task.id if task else None,
                           context_id=task.context_id if task else None)
    async for event in client.send_message(SendMessageRequest(message=msg)):
        return event.task


async def main():
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=PORT, log_level='critical'))
    serving = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)
    client = await create_client(card_for('/stops'), client_config=ClientConfig(streaming=False))
    print('[1] send "Convert 100 USD"')                       # the job is missing the target currency
    task = await send(client, 'Convert 100 USD')
    print(f'    task {task.id[:8]}  {state(task.status.state)}: "{get_message_text(task.status.message)}"')
    print('[2] answer "EUR" with the same task ID')
    task = await send(client, 'EUR', task)
    print(f'    task {task.id[:8]}  {state(task.status.state)}: {get_artifact_text(task.artifacts[0])}')

    print('[3] start a long job, then cancel it (executor stops the work)')
    quick = await create_client(card_for('/stops'), client_config=ClientConfig(streaming=False, polling=True))
    job = await send(quick, 'Convert every price list')        # polling: returns without waiting
    print(f'    task {job.id[:8]}  {state(job.status.state)}')
    done = await quick.cancel_task(CancelTaskRequest(id=job.id))
    print(f'    after cancel: {state(done.status.state)}')

    print('[4] same, but this executor refuses to cancel')                 # way 2
    refuser = await create_client(card_for('/refuses'), client_config=ClientConfig(streaming=False, polling=True))
    job = await send(refuser, 'Convert every price list')
    try:
        await refuser.cancel_task(CancelTaskRequest(id=job.id))
    except Exception as e:
        print(f'    caller gets: {type(e).__name__}: {e}')
    left = await refuser.get_task(GetTaskRequest(id=job.id))
    print(f'    task state the SDK leaves behind: {state(left.status.state)}')

    await asyncio.gather(client.close(), quick.close(), refuser.close())
    server.should_exit = True
    await serving


asyncio.run(main())
