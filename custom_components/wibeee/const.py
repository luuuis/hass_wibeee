from datetime import timedelta

DOMAIN = 'wibeee'
NEST_DEFAULT_UPSTREAM = 'http://nest-ingest.wibeee.com'
PROXY_PORT = 8600

DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)
DEFAULT_TIMEOUT = timedelta(seconds=10)

CONF_NEST_PROXY_ENABLE = 'nest_proxy_enable'
CONF_NEST_PROXY_PORT = 'nest_proxy_port'
CONF_NEST_UPSTREAM = 'nest_upstream'

NEST_UPSTREAMS = [
    'http://nest-ingest.wibeee.com',
    'http://wdata.solarprofit.es:8080'
]
