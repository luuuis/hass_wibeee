from datetime import timedelta

from homeassistant.helpers.selector import SelectOptionDict

DOMAIN = 'wibeee'
NEST_DEFAULT_UPSTREAM = 'http://nest-ingest.wibeee.com'

DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)
DEFAULT_TIMEOUT = timedelta(seconds=10)

CONF_NEST_UPSTREAM = 'nest_upstream'


def _format_options(upstreams: dict[str, str]) -> list[SelectOptionDict]:
    return [SelectOptionDict(label=f'{cloud} ({url})', value=url) for cloud, url in upstreams.items()]


NEST_PROXY_DISABLED: str = 'proxy_disabled'
NEST_NULL_UPSTREAM: str = 'proxy_null'
NEST_ALL_UPSTREAMS: list[SelectOptionDict] = [SelectOptionDict(label='Disabled (polling only)', value=NEST_PROXY_DISABLED),
                                              SelectOptionDict(label='Local only (no Cloud)', value=NEST_NULL_UPSTREAM)] + \
                                             _format_options({
                                                 'Wibeee Nest': NEST_DEFAULT_UPSTREAM,
                                                 'Iberdrola': 'http://datosmonitorconsumo.iberdrola.es:8080',
                                                 'SolarProfit': 'http://wdata.solarprofit.es:8080',
                                             })
