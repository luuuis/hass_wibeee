from datetime import timedelta

from homeassistant.helpers.selector import SelectOptionDict

DOMAIN = 'wibeee'
NEST_DEFAULT_UPSTREAM = 'http://nest-ingest.wibeee.com'
PROXY_PORT = 8600

DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)
DEFAULT_TIMEOUT = timedelta(seconds=10)

CONF_NEST_PROXY_ENABLE = 'nest_proxy_enable'
CONF_NEST_UPSTREAM = 'nest_upstream'


def _format_options(upstreams: dict[str, str]) -> list[SelectOptionDict]:
    return [SelectOptionDict(label=f'{cloud} ({url})', value=url) for cloud, url in upstreams.items()]


NEST_NULL_UPSTREAM: SelectOptionDict = SelectOptionDict(label='Disabled', value='disabled')
NEST_ALL_UPSTREAMS: list[SelectOptionDict] = [NEST_NULL_UPSTREAM] + _format_options({
    'Wibeee Nest': NEST_DEFAULT_UPSTREAM,
    'SolarProfit': 'http://wdata.solarprofit.es:8080',
})
