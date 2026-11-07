"""Lab 20 (video section s20): securing your agent.

Three decisions: how callers sign in, what each caller may do, what your card shows.
- Sign-in: the card lists the methods you accept (API key, HTTP auth such as a bearer
  token, OAuth 2.0, OpenID Connect, mutual TLS). This lab uses a bearer token as one
  example, checked by plain Starlette middleware in front of the A2A routes.
  Credentials travel with each request, not inside the A2A message.
- Per caller: one caller can't see another caller's tasks, and such a task looks the
  same as one that doesn't exist.
The spec says production deployments MUST use encryption (HTTPS); this lab is plain
HTTP on 127.0.0.1 only.
"""
import asyncio, socket
import httpx, uvicorn
from starlette.applications import Starlette
from starlette.authentication import AuthCredentials, AuthenticationBackend, AuthenticationError, SimpleUser
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.responses import JSONResponse
from a2a.client import ClientConfig, create_client
from a2a.helpers import new_task_from_user_message, new_text_message
from a2a.server.agent_execution import AgentExecutor
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (AgentCapabilities, AgentCard, AgentInterface, AgentSkill, CancelTaskRequest, GetTaskRequest,
                       HTTPAuthSecurityScheme, Role, SecurityRequirement, SecurityScheme,
                       SendMessageRequest, StringList, TaskState)

with socket.socket() as s:
    s.bind(('127.0.0.1', 0)); PORT = s.getsockname()[1]
URL = f'http://127.0.0.1:{PORT}'
EXAMPLE_TOKENS = {'example-token-alice': 'alice', 'example-token-bob': 'bob'}   # examples only


class BearerCheck(AuthenticationBackend):        # every A2A request is checked; the public card stays open
    async def authenticate(self, conn):
        if conn.url.path == '/.well-known/agent-card.json':
            return None
        token = conn.headers.get('authorization', '').removeprefix('Bearer ')
        if token not in EXAMPLE_TOKENS:
            raise AuthenticationError('missing or unknown bearer token')
        return AuthCredentials(['authenticated']), SimpleUser(EXAMPLE_TOKENS[token])


class Done(AgentExecutor):
    async def execute(self, context, event_queue):
        task = new_task_from_user_message(context.message)
        await event_queue.enqueue_event(task)
        await TaskUpdater(event_queue, task.id, task.context_id).update_status(TaskState.TASK_STATE_COMPLETED)
    async def cancel(self, context, event_queue): ...


card = AgentCard(
    name='Secured Agent', description='Shows sign-in and per-caller tasks.', version='1.0.0',
    default_input_modes=['text/plain'], default_output_modes=['text/plain'],
    capabilities=AgentCapabilities(streaming=False),
    supported_interfaces=[AgentInterface(protocol_binding='JSONRPC', url=URL, protocol_version='1.0')],
    security_schemes={'bearer': SecurityScheme(http_auth_security_scheme=HTTPAuthSecurityScheme(
        scheme='Bearer'))},
    security_requirements=[SecurityRequirement(schemes={'bearer': StringList()})],
    skills=[AgentSkill(id='done', name='Done', description='Completes at once.', tags=['demo'])])
# The SDK's InMemoryTaskStore keeps each task under its owner (by default: the signed-in user's
# name), and a lookup by anyone else finds nothing. Your own authorization rules can go further.
handler = DefaultRequestHandler(agent_executor=Done(), task_store=InMemoryTaskStore(), agent_card=card)
app = Starlette(routes=[*create_agent_card_routes(card), *create_jsonrpc_routes(handler, '/')],
                middleware=[Middleware(AuthenticationMiddleware, backend=BearerCheck(),
                            on_error=lambda conn, e: JSONResponse({'error': str(e)}, status_code=401,
                                                                  headers={'WWW-Authenticate': 'Bearer'}))])


async def as_caller(token):
    http = httpx.AsyncClient(headers={'Authorization': f'Bearer {token}'})   # credential on every request
    return await create_client(card, client_config=ClientConfig(streaming=False, httpx_client=http))


async def attempt(call):
    try:
        await call
        return 'ok'
    except Exception as e:
        return f'{type(e).__name__}: {e}'


async def main():
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=PORT, log_level='warning'))
    serving = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)
    async with httpx.AsyncClient() as http:
        print('[1] the card lists how to sign in')
        print(f"    {(await http.get(f'{URL}/.well-known/agent-card.json')).json()['securitySchemes']}")
        print('[2] SendMessage with no token')
        r = await http.post(URL + '/', headers={'A2A-Version': '1.0'}, json={'jsonrpc': '2.0', 'id': 1,
            'method': 'SendMessage', 'params': {'message': {'role': 'ROLE_USER', 'messageId': 'm1',
                                                            'parts': [{'text': 'hi'}]}}})
        print(f"    HTTP {r.status_code}  WWW-Authenticate: {r.headers.get('www-authenticate')}  {r.json()}")

    alice, bob = await as_caller('example-token-alice'), await as_caller('example-token-bob')
    async for event in alice.send_message(SendMessageRequest(message=new_text_message('hi', role=Role.ROLE_USER))):
        task_id = event.task.id
    print(f'[3] alice (token) creates task {task_id[:8]}')
    print(f'    alice gets her task:        {await attempt(alice.get_task(GetTaskRequest(id=task_id)))}')
    print(f"    bob gets alice's task:      {await attempt(bob.get_task(GetTaskRequest(id=task_id)))}")
    print(f"    bob cancels alice's task:   {await attempt(bob.cancel_task(CancelTaskRequest(id=task_id)))}")
    print(f'    bob gets a made-up task ID: {await attempt(bob.get_task(GetTaskRequest(id="no-such-task")))}')
    print('    -> the same answer: bob cannot tell whether the task exists')
    await alice.close(); await bob.close()
    server.should_exit = True
    await serving


asyncio.run(main())
