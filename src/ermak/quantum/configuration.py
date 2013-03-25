from configobj import ConfigObj
from quantum.common.utils import find_config_file

_CONF_FILE = find_config_file({'plugin': 'udp_socket_plugin'},
    "udp_socket_plugin.ini")
_CONF_PARSER_OBJ = ConfigObj(_CONF_FILE)

_DB_CONF = _CONF_PARSER_OBJ['DATABASE']

DB_SQL_CONNECTION = _DB_CONF['sql_connection']
DB_RECONNECT_INTERVAL = int(_DB_CONF.get('reconnect_interval', 2))


_DB_CONF = _CONF_PARSER_OBJ['UDP_POOL']
UDP_POOL_CIDR = str(_DB_CONF.get('cidr'))
UDP_PORT = int(_DB_CONF.get('port'))
