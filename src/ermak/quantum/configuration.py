from configobj import ConfigObj
from quantum.common.config import find_config_file

_CONF_FILE = find_config_file({'plugin': 'dynamips_bridge'}, None,
    "dynamips_bridge_plugin.ini")
_CONF_PARSER_OBJ = ConfigObj(_CONF_FILE)

_DB_CONF = _CONF_PARSER_OBJ['DATABASE']

DB_SQL_CONNECTION = _DB_CONF['sql_connection']
DB_RECONNECT_INTERVAL = int(_DB_CONF.get('reconnect_interval', 2))


_DYNAMIPS_CONF = _CONF_PARSER_OBJ['DYNAMIPS']

DYNAMIPS_PORT = int(_DYNAMIPS_CONF.get('port', 7200))
DYNAMIPS_HOST = _DYNAMIPS_CONF.get('host', 'localhost')