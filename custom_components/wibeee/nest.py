import logging
from typing import Callable, Dict, Tuple
from urllib.parse import parse_qsl

from homeassistant.components.network import async_get_source_ip
from homeassistant.components.network.const import PUBLIC_TARGET_IP
from homeassistant.core import callback
from homeassistant.helpers import singleton
from homeassistant.helpers.typing import EventType

LOGGER = logging.getLogger(__name__)

import aiohttp
from aiohttp import web
from aiohttp.web_routedef import _HandlerType

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.core import HomeAssistant
from homeassistant.const import EVENT_HOMEASSISTANT_STOP


class NestProxy(object):
    _listeners = {}

    def register_device(self, mac_address: str, listener: Callable[[Dict], None]):
        self._listeners[mac_address] = listener

    def unregister_device(self, mac_address: str):
        self._listeners.pop(mac_address)

    def dispatch(self, mac_addr: str, pushed_data: Dict):
        if mac_addr in self._listeners:
            self._listeners[mac_addr](pushed_data)
        else:
            LOGGER.debug("Ignoring pushed data from %s: %s", mac_addr, pushed_data)


@singleton.singleton("wibeee_nest_proxy")
async def get_nest_proxy(
        hass: HomeAssistant,
        upstream='http://nest-ingest.wibeee.com',
        local_port=8600,
) -> NestProxy:
    session = async_get_clientsession(hass)
    nest_proxy = NestProxy()

    def nest_forward(snoop_data: Callable[[web.Request], Tuple[str, Dict]] = None) -> _HandlerType:
        async def handler(req: web.Request) -> web.StreamResponse:
            url = f'{upstream}{req.path}?{req.query_string}'
            req_body = (await req.read()) if req.can_read_body else None

            res = await session.request(req.method, url, data=req_body)
            res_body = await res.read()

            if snoop_data:
                mac_addr, push_data = snoop_data(req)
                nest_proxy.dispatch(mac_addr, push_data)

            return web.Response(headers=res.headers, body=res_body)

        return handler

    def extract_query_params(req: web.Request) -> Tuple[str, Dict]:
        """Extracts Wibeee data from query params."""
        query = {k: v for k, v in parse_qsl(req.query_string)}
        return query['mac'], query

    app = aiohttp.web.Application()
    app.add_routes([
        web.get('/Wibeee/receiverLeap', nest_forward(extract_query_params)),
        web.route('*', '/{anypath:.*}', nest_forward()),
    ])

    # don't listen on public IP
    local_ip = await async_get_source_ip(hass, target_ip=PUBLIC_TARGET_IP)

    # access log only if DEBUG level is enabled
    access_log = logging.getLogger(f'{__name__}.access')
    access_log.setLevel(access_log.getEffectiveLevel() + 10)

    server = hass.loop.create_task(web._run_app(app, host=local_ip, port=local_port, access_log=access_log))
    LOGGER.info('Wibeee Nest proxy listening on http://%s:%d', local_ip, local_port)

    @callback
    def shutdown_proxy(ev: EventType) -> None:
        LOGGER.info('Wibeee Nest proxy shutting down')
        server.cancel()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown_proxy)
    return nest_proxy
