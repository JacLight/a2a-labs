"""Lab 23 (video section s23): versions and extensions.

Versions: a client sends the A2A version it speaks with every request, in the
A2A-Version header (current: 1.0). An agent that doesn't support it returns
VersionNotSupportedError instead of guessing.
Extensions: the agent lists them in its card; a client opts in per request with
the A2A-Extensions header. If a card marks an extension as required and the
caller doesn't declare it, the agent returns ExtensionSupportRequiredError.
The extension URIs are the spec's own examples; marking citations "required" is ours.
"""
import asyncio, logging, socket
import httpx, uvicorn
from google.protobuf.json_format import MessageToDict
from starlette.applications import Starlette
from a2a.client import ClientCallContext, ClientConfig, create_client
from a2a.helpers import get_message_text, new_text_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (AgentCapabilities, AgentCard, AgentExtension, AgentInterface, AgentSkill, Role,
                       SendMessageRequest)
from a2a.utils.errors import ExtensionSupportRequiredError

with socket.socket() as s:
    s.bind(('127.0.0.1', 0)); PORT = s.getsockname()[1]
URL = f'http://127.0.0.1:{PORT}'
logging.getLogger('a2a').setLevel(logging.CRITICAL)   # hide the SDK's own warning/traceback logs
GEO, CITE = 'https://example.com/extensions/geolocation/v1', 'https://standards.org/extensions/citations/v1'

card = AgentCard(
    name='Research Assistant Agent', description='Finds places, with sources.', version='1.0.0',
    default_input_modes=['text/plain'], default_output_modes=['text/plain'],
    capabilities=AgentCapabilities(streaming=False, extensions=[                # declared in the card
        AgentExtension(uri=GEO, description='Location-based search', required=False),
        AgentExtension(uri=CITE, description='Citation formatting', required=True)]),
    supported_interfaces=[AgentInterface(protocol_binding='JSONRPC', url=URL, protocol_version='1.0')],
    skills=[AgentSkill(id='search', name='Search', description='Finds places.', tags=['search'])])


class Researcher(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue) -> None:
        # a2a-sdk 1.3.0 hands you the opted-in URIs (context.requested_extensions) but does NOT
        # check "required" for you. This check is ours, written to follow the spec.
        for ext in card.capabilities.extensions:
            if ext.required and ext.uri not in context.requested_extensions:
                raise ExtensionSupportRequiredError(message=f'This agent requires {ext.uri}')
        version = context.call_context.state['headers'].get('a2a-version')
        where = MessageToDict(context.message.metadata).get(GEO)          # the extension's data, if sent
        place = f"near {where['latitude']}, {where['longitude']}" if where else '(no location sent)'
        await event_queue.enqueue_event(new_text_message(f'[saw A2A-Version {version}] searching {place}'))

    async def cancel(self, context, event_queue): ...


handler = DefaultRequestHandler(agent_executor=Researcher(), task_store=InMemoryTaskStore(), agent_card=card)
app = Starlette(routes=[*create_agent_card_routes(card), *create_jsonrpc_routes(handler, '/')])
BODY = {'jsonrpc': '2.0', 'id': 1, 'method': 'SendMessage',
        'params': {'message': {'role': 'ROLE_USER', 'messageId': 'm1', 'parts': [{'text': 'Hello'}]}}}


async def main():
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=PORT, log_level='critical'))
    serving = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)

    print('[1] plain httpx SendMessage with different A2A-Version headers')
    async with httpx.AsyncClient() as http:
        for version in ['1.0', '0.5', '1.1', None]:
            headers = {'A2A-Version': version, 'A2A-Extensions': CITE} if version else {'A2A-Extensions': CITE}
            reply = (await http.post(URL, json=BODY, headers=headers)).json()
            err = reply.get('error')
            result = f"error {err['code']}: {err['message']}" if err else 'ok'
            print(f"    A2A-Version {version or '(none)':<6} -> {result}")
    # The spec: match Major.Minor, and read an empty header as 0.3. What 1.3.0 really does: it reads
    # no header as 0.3 (refused here; the routes take enable_v0_3_compat=True to serve 0.3 callers),
    # but it compares only the major number, so 1.1 is accepted and handled as 1.0.

    print('[2] SDK client (adds A2A-Version itself), opting in to both extensions')
    client = await create_client(card, client_config=ClientConfig(streaming=False))
    msg = new_text_message('Find restaurants near me', role=Role.ROLE_USER)
    msg.extensions.append(GEO)
    msg.metadata.update({GEO: {'latitude': 37.7749, 'longitude': -122.4194}})   # the extension's data
    both = ClientCallContext(service_parameters={'A2A-Extensions': f'{GEO},{CITE}'})
    async for event in client.send_message(SendMessageRequest(message=msg), context=both):
        print(f'    reply: {get_message_text(event.message)}')

    print('[3] same request, opting in to geolocation only (citations is required)')
    geo_only = ClientCallContext(service_parameters={'A2A-Extensions': GEO})
    try:
        async for event in client.send_message(SendMessageRequest(message=msg), context=geo_only):
            print(f'    reply: {get_message_text(event.message)}')
    except Exception as e:
        print(f'    caller gets: {type(e).__name__}: {e}')
    await client.close()
    server.should_exit = True
    await serving


asyncio.run(main())
