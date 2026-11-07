"""Lab 11 (video section s11): finding an agent to call.

Your agent fetches the remote agent's card from its well-known path, reads it
the way it will use it (skills, content types, capabilities, sign-in), then
creates its client from the card. Run: python lab11_discover.py
"""
import asyncio, socket
import httpx, uvicorn
from starlette.applications import Starlette
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.server.agent_execution import AgentExecutor
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes, create_rest_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (AgentCapabilities, AgentCard, AgentInterface, AgentSkill,
                       OpenIdConnectSecurityScheme, SecurityRequirement, SecurityScheme, StringList)
from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH

# --- your agent: the client side ---
JOB_TAG, HAVE, NEED = 'route-planning', 'text/plain', 'application/json'

async def main():
    async with httpx.AsyncClient(timeout=10) as http:
        # [1] The standard place to look: the agent's own domain, at the well-known path.
        #     (A registry or your own config are other ways a card can reach you.)
        print(f'[1] fetch the card from {AGENT_CARD_WELL_KNOWN_PATH}')
        card = await A2ACardResolver(httpx_client=http, base_url=URL).get_agent_card()
        print(f'    got: {card.name} {card.version}')

        # [2] Do its skills match the job?
        skill = next((s for s in card.skills if JOB_TAG in s.tags), None)
        print(f'[2] skill for "{JOB_TAG}": {skill.name if skill else "none, look elsewhere"}')

        # [3] Does it take the content you have, and return what you need?
        #     A skill may list its own modes; if it doesn't, the card's defaults apply.
        ins = list(skill.input_modes or card.default_input_modes)
        outs = list(skill.output_modes or card.default_output_modes)
        print(f'[3] takes {HAVE}: {HAVE in ins}   returns {NEED}: {NEED in outs}')

        # [4] Streaming or push notifications, if you'll want them.
        caps = card.capabilities
        print(f'[4] streaming: {caps.streaming}   push notifications: {caps.push_notifications}')

        # [5] Which sign-in does it require? The card names the schemes; getting
        #     a token from that provider happens outside A2A.
        for req in card.security_requirements:
            for name, scopes in req.schemes.items():
                scheme = card.security_schemes[name]
                print(f'[5] sign-in: {scheme.WhichOneof("scheme")} "{name}", scopes {list(scopes.list)}')

        # [6] Create the client from the card. It walks the card's interfaces in
        #     order and uses the first one this client supports (JSON-RPC only, here).
        print('[6] card interfaces:', [i.protocol_binding for i in card.supported_interfaces])
        client = await create_client(card, client_config=ClientConfig(httpx_client=http, streaming=False))
        t = client._transport          # private attribute, read only to show the choice
        print(f'    client picked: {type(t).__name__} at {t.url}')
        await client.close()

# --- the remote agent (stand-in) ---
# It only needs to serve its card for this lab. It declares an OpenID Connect
# sign-in but does not check it: a real agent would.
class Idle(AgentExecutor):
    async def execute(self, context, event_queue): pass
    async def cancel(self, context, event_queue): pass

with socket.socket() as s:
    s.bind(('127.0.0.1', 0)); PORT = s.getsockname()[1]
URL = f'http://127.0.0.1:{PORT}'
card = AgentCard(
    name='Route Planner', description='Plans routes between places.', version='1.2.0',
    default_input_modes=['text/plain'], default_output_modes=['application/json', 'text/plain'],
    capabilities=AgentCapabilities(streaming=True, push_notifications=True),
    supported_interfaces=[  # preference order: REST first, then JSON-RPC
        AgentInterface(protocol_binding='HTTP+JSON', url=f'{URL}/rest', protocol_version='1.0'),
        AgentInterface(protocol_binding='JSONRPC', url=URL, protocol_version='1.0')],
    security_schemes={'oidc': SecurityScheme(open_id_connect_security_scheme=OpenIdConnectSecurityScheme(
        open_id_connect_url='https://accounts.example.com/.well-known/openid-configuration'))},
    security_requirements=[SecurityRequirement(schemes={'oidc': StringList(list=['openid', 'profile'])})],
    skills=[AgentSkill(id='plan-route', name='Plan a route', description='Plans a route between two places.',
                       tags=['route-planning', 'maps'], examples=['Fastest route from Lagos to Ibadan'])])
handler = DefaultRequestHandler(agent_executor=Idle(), task_store=InMemoryTaskStore(), agent_card=card)
app = Starlette(routes=[*create_agent_card_routes(card), *create_jsonrpc_routes(handler, '/'),
                        *create_rest_routes(handler, path_prefix='/rest')])

# --- run both, then shut down ---
async def run():
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=PORT, log_level='warning'))
    serving = asyncio.create_task(server.serve())
    while not server.started: await asyncio.sleep(0.05)
    try: await main()
    finally:
        await handler.aclose(); server.should_exit = True; await serving

asyncio.run(run())
