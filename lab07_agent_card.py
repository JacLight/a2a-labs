"""Lab 07 (video section s07): writing your Agent Card.

Callers read the card to decide whether to send your agent a job. It lists your
skills, the content you take and return, the extras you support, where you can
be reached and how callers sign in. The SDK serves it at /.well-known/agent-card.json.
Extra details for signed-in callers go in an extended card.
"""
import asyncio, socket
import httpx, uvicorn
from starlette.applications import Starlette
from starlette.authentication import (AuthCredentials, AuthenticationBackend,
                                      AuthenticationError, SimpleUser)
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.responses import JSONResponse
from a2a.client import ClientConfig, create_client
from a2a.server.agent_execution import AgentExecutor
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (AgentCapabilities, AgentCard, AgentInterface, AgentSkill, GetExtendedAgentCardRequest,
                       HTTPAuthSecurityScheme, SecurityRequirement, SecurityScheme, StringList)

with socket.socket() as s:
    s.bind(('127.0.0.1', 0)); PORT = s.getsockname()[1]
URL = f'http://127.0.0.1:{PORT}'
EXAMPLE_TOKEN = 'example-token-123'              # an example only; real tokens come from your sign-in system

echo = AgentSkill(id='echo_bot', name='Echo Bot', tags=['echo'],                 # 1. skills
                  description='Acknowledges your request with a hello.', examples=['hi', 'how are you'])
super_echo = AgentSkill(id='echo_bot_super_mode', name='Echo Bot (Super Mode)', tags=['echo'],
                        description='Replies with extra enthusiasm.', examples=['super hi'])
card = AgentCard(
    name='Hello World Agent', description='Just a hello world agent', version='0.0.1',
    default_input_modes=['text/plain'], default_output_modes=['text/plain'],    # 2. content in and out
    capabilities=AgentCapabilities(streaming=True, push_notifications=False,    # 3. extras
                                   extended_agent_card=True),
    supported_interfaces=[AgentInterface(protocol_binding='JSONRPC', url=URL,    # 4. where to reach it
                                         protocol_version='1.0')],
    security_schemes={'bearer': SecurityScheme(                                  # 5. how to sign in
        http_auth_security_scheme=HTTPAuthSecurityScheme(scheme='Bearer'))},     #    (one of several kinds)
    security_requirements=[SecurityRequirement(schemes={'bearer': StringList()})],
    skills=[echo])
extended = AgentCard()
extended.CopyFrom(card)
extended.name = 'Hello World Agent - Extended Edition'
extended.skills.append(super_echo)                                             # extra skill, signed-in only


class Unused(AgentExecutor):                     # this lab sends no jobs; lab 06 and lab 08 do
    async def execute(self, context, event_queue): ...
    async def cancel(self, context, event_queue): ...


# The spec says fetching the extended card MUST require authentication. The SDK serves it to any
# request that reaches the route, so the sign-in check is yours: here, plain Starlette middleware.
class BearerCheck(AuthenticationBackend):        # the public card stays open,
    async def authenticate(self, conn):          # every A2A call needs the token
        if conn.url.path == '/.well-known/agent-card.json':
            return None
        if conn.headers.get('authorization') != f'Bearer {EXAMPLE_TOKEN}':
            raise AuthenticationError('missing or wrong bearer token')
        return AuthCredentials(['authenticated']), SimpleUser('caller-a')


handler = DefaultRequestHandler(agent_executor=Unused(), task_store=InMemoryTaskStore(),
                                agent_card=card, extended_agent_card=extended)
app = Starlette(routes=[*create_agent_card_routes(card), *create_jsonrpc_routes(handler, '/')],
                middleware=[Middleware(AuthenticationMiddleware, backend=BearerCheck(),
                            on_error=lambda conn, e: JSONResponse({'error': str(e)}, status_code=401))])


async def main():
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=PORT, log_level='warning'))
    serving = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)

    print('[1] fetch the card with plain httpx: GET /.well-known/agent-card.json')
    async with httpx.AsyncClient() as http:
        c = (await http.get(f'{URL}/.well-known/agent-card.json')).json()
    print(f"    name:         {c['name']} {c['version']}")
    for sk in c['skills']:
        print(f"    skill:        {sk['name']}: {sk['description']}  examples {sk['examples']}")
    print(f"    takes/returns {c['defaultInputModes']} -> {c['defaultOutputModes']}")
    print(f"    capabilities: {c['capabilities']}")
    for i in c['supportedInterfaces']:
        print(f"    interface:    {i['protocolBinding']} {i['url']} (A2A {i['protocolVersion']})")
    print(f"    sign-in:      {c['securitySchemes']}")

    print('[2] ask for the extended card WITHOUT a token')
    anon = await create_client(card, client_config=ClientConfig(streaming=False))
    try:
        await anon.get_extended_agent_card(GetExtendedAgentCardRequest())
    except Exception as e:
        print(f'    refused: {type(e).__name__}: {str(e).splitlines()[0]}')
    await anon.close()

    print('[3] ask for the extended card WITH the example token')
    http = httpx.AsyncClient(headers={'Authorization': f'Bearer {EXAMPLE_TOKEN}'})
    signed_in = await create_client(card, client_config=ClientConfig(streaming=False, httpx_client=http))
    ext = await signed_in.get_extended_agent_card(GetExtendedAgentCardRequest())
    print(f'    name:   {ext.name}')
    print(f'    skills: {[sk.name for sk in ext.skills]}')
    await http.aclose()

    server.should_exit = True
    await serving


asyncio.run(main())
