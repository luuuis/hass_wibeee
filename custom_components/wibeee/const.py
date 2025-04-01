from datetime import timedelta

from homeassistant.helpers.selector import SelectOptionDict

DOMAIN = 'wibeee'
NEST_DEFAULT_UPSTREAM = 'http://nest-ingest.wibeee.com'

DEFAULT_TIMEOUT = timedelta(seconds=10)

CONF_NEST_UPSTREAM = 'nest_upstream'

CONF_MAC_ADDRESS = 'mac_address'
"""Device's MAC address."""

CONF_WIBEEE_ID = 'wibeee_id'
"""Device's Wibeee ID, used for polling values.xml API."""


def _format_options(upstreams: dict[str, str]) -> list[SelectOptionDict]:
    return [SelectOptionDict(label=f'{cloud} ({url})', value=url) for cloud, url in upstreams.items()]


NEST_NULL_UPSTREAM: str = 'proxy_null'
NEST_ALL_UPSTREAMS: list[SelectOptionDict] = [SelectOptionDict(label='Local only (no Cloud)', value=NEST_NULL_UPSTREAM)] + \
                                             _format_options({
                                                 'Wibeee Nest': NEST_DEFAULT_UPSTREAM,
                                                 'Iberdrola': 'http://datosmonitorconsumo.iberdrola.es:8080',
                                                 'SolarProfit': 'http://wdata.solarprofit.es:8080',
                                             })
