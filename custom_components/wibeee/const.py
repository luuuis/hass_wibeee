from datetime import timedelta

DOMAIN = 'wibeee'
NEST_URL = 'http://nest-ingest.wibeee.com'
NEST_PORT = 80
PROXY_PORT = 8600

DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)
DEFAULT_TIMEOUT = timedelta(seconds=10)

CONF_NEST_PROXY_ENABLE = 'nest_proxy_enable'
CONF_NEST_PROXY_PORT = 'nest_proxy_port'
CONF_NEST_UPSTREAM_URL = 'nest_upstream_url'
CONF_NEST_UPSTREAM_PORT = 'nest_upstream_port'
