"""Lab 18 (video section s18): callbacks with push notifications. Run: python lab18_push.py

Check the card, give the agent a webhook address and the credentials it should use
(here in the first message; it can also be added to a task later). Your webhook replies
with a success code, checks the credentials and the task ID, ignores duplicates, then
fetches the task. Agent side: checking webhook addresses."""
import asyncio, json, logging, socket, httpx, uvicorn
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import new_task_from_user_message, new_text_message, new_text_part
from a2a.server.agent_execution import AgentExecutor
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import (BasePushNotificationSender, InMemoryPushNotificationConfigStore,
                              InMemoryTaskStore, TaskUpdater)
from a2a.types import (AgentCapabilities, AgentCard, AgentInterface, AgentSkill, AuthenticationInfo,
                       GetTaskRequest, Role, SendMessageConfiguration, SendMessageRequest,
                       TaskPushNotificationConfig, TaskState, TaskStatusUpdateEvent)
from a2a.utils.push_url_validator import validate_push_notification_url

def free_port():
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); return s.getsockname()[1]
# --- your agent: the client side (sender + webhook) ---
HOOK_PORT = free_port(); WEBHOOK = f'http://127.0.0.1:{HOOK_PORT}/webhook/a2a-notifications'
SECRET = 'webhook-secret-123'                 # what the agent must present when it calls you
started, seen, inbox = set(), set(), asyncio.Queue()

async def webhook(request):                   # your webhook receiver
    if request.headers.get('authorization') != f'Bearer {SECRET}':
        return Response(status_code=401)      # check the credentials
    await inbox.put(await request.json())     # acknowledge fast; process below
    return Response(status_code=200)          # the success code

def check(body):
    kind, ev = next(iter(body.items()))       # a StreamResponse: task / statusUpdate / artifactUpdate
    if (ev.get('taskId') or ev.get('id')) not in started:
        return f'{kind:<14} task "{ev.get("taskId")}": not one I started, ignored'
    key = json.dumps(body, sort_keys=True)
    if key in seen: return f'{kind:<14} duplicate, ignored'
    seen.add(key)
    return f'{kind:<14} ' + ev.get('status', {}).get('state', 'artifact ready').removeprefix('TASK_STATE_')

hook_app = Starlette(routes=[Route('/webhook/a2a-notifications', webhook, methods=['POST'])])

async def main():
    async with httpx.AsyncClient(timeout=10) as http:
        card = await A2ACardResolver(http, URL).get_agent_card()
        print(f'[1] card says push notifications: {card.capabilities.push_notifications}')
        client = await create_client(card, client_config=ClientConfig(httpx_client=http, streaming=False))

        print('[2] send the job with a webhook address and credentials; no open connection')
        push = TaskPushNotificationConfig(url=WEBHOOK, authentication=AuthenticationInfo(scheme='Bearer', credentials=SECRET))
        req = SendMessageRequest(message=new_text_message('Weekly sales report', role=Role.ROLE_USER),
            configuration=SendMessageConfiguration(task_push_notification_config=push, return_immediately=True))
        task = [r async for r in client.send_message(req)][-1].task
        started.add(task.id)
        print(f'    task {task.id[:8]}.. {TaskState.Name(task.status.state)}')

        r = await http.post(WEBHOOK, json={'statusUpdate': {'taskId': task.id}},
                            headers={'Authorization': 'Bearer guess'})
        print(f'    a call with the wrong credentials gets {r.status_code}')
        await http.post(WEBHOOK, json={'statusUpdate': {'taskId': 'not-mine'}},     # right credentials,
                        headers={'Authorization': f'Bearer {SECRET}'})              # someone else's task

        print('[3] what reaches the webhook (until it goes quiet for 1 s)')
        while True:
            try: print('   ', check(await asyncio.wait_for(inbox.get(), 1.0)))
            except asyncio.TimeoutError: break
        full = await client.get_task(GetTaskRequest(id=task.id))     # then fetch the full result
        print(f'    GetTask: {TaskState.Name(full.status.state)}, artifact "{full.artifacts[0].parts[0].text}"')

        print('[4] agent side: checking the webhook addresses callers give')
        for url in ['http://10.0.0.5/hook', 'http://169.254.169.254/latest', 'http://127.0.0.1:22/']:
            print(f'    {url:<32} SDK check allows: {await validate_push_notification_url(url)}')
        bad = SendMessageConfiguration(task_push_notification_config=TaskPushNotificationConfig(url='http://192.168.1.10/hook'))
        try: [r async for r in client.send_message(SendMessageRequest(message=req.message, configuration=bad))]
        except Exception as e:
            print(f'    register http://192.168.1.10/hook -> {type(e).__name__}: {e}')
        await client.close()

# --- the remote agent (stand-in) ---
class ReportAgent(AgentExecutor):
    async def execute(self, ctx, q):
        task = new_task_from_user_message(ctx.message); await q.enqueue_event(task)
        up = TaskUpdater(q, task.id, task.context_id)
        await asyncio.sleep(0.5); await up.start_work(); await asyncio.sleep(0.3)
        await up.add_artifact([new_text_part('Sales up 6% week on week.')], name='report')
        await up.complete()
    async def cancel(self, ctx, q): pass

async def allowed(url):
    # The spec says agents SHOULD validate webhook URLs against SSRF: reject private ranges,
    # localhost and link-local; allow-lists where appropriate. The SDK's check rejects them.
    # This lab's own webhook is on 127.0.0.1, so it is allow-listed by exact address.
    return url == WEBHOOK or await validate_push_notification_url(url)

class RetryingSender(BasePushNotificationSender):  # stand-in: sends the final update twice, like a retry
    async def send_notification(self, task_id, event):
        await super().send_notification(task_id, event)
        if isinstance(event, TaskStatusUpdateEvent) and event.status.state == TaskState.TASK_STATE_COMPLETED:
            await super().send_notification(task_id, event)

PORT = free_port(); URL = f'http://127.0.0.1:{PORT}'
card = AgentCard(name='Report Agent', description='Builds sales reports.', version='1.0.0',
    default_input_modes=['text/plain'], default_output_modes=['text/plain'],
    capabilities=AgentCapabilities(streaming=False, push_notifications=True),
    supported_interfaces=[AgentInterface(protocol_binding='JSONRPC', url=URL, protocol_version='1.0')],
    skills=[AgentSkill(id='report', name='Sales report', description='Builds a sales report.', tags=['sales'])])
configs = InMemoryPushNotificationConfigStore()
handler = DefaultRequestHandler(agent_executor=ReportAgent(), task_store=InMemoryTaskStore(), agent_card=card,
    push_config_store=configs, push_url_validator=allowed,
    push_sender=RetryingSender(httpx.AsyncClient(timeout=10), configs, push_url_validator=allowed))
app = Starlette(routes=[*create_agent_card_routes(card), *create_jsonrpc_routes(handler, '/')])
logging.getLogger('a2a.utils.push_url_validator').setLevel(logging.ERROR)  # we print the result instead

# --- run both, then shut down ---
async def run():
    servers = [uvicorn.Server(uvicorn.Config(a, host='127.0.0.1', port=p, log_level='warning'))
               for a, p in ((app, PORT), (hook_app, HOOK_PORT))]
    serving = [asyncio.create_task(s.serve()) for s in servers]
    while not all(s.started for s in servers): await asyncio.sleep(0.05)
    try: await main()
    finally:
        await handler.aclose()
        for s in servers: s.should_exit = True
        await asyncio.gather(*serving)

asyncio.run(run())
