import logging
from quantum.db import models_v2

from quantum.db.db_base_plugin_v2 import QuantumDbPluginV2
from quantum.db import api as db

from ermak.quantum import configuration
from ermak.quantum import db as plugin_db


LOG = logging.getLogger("quantum.plugin.dynamips_udp")

class UdpSocketPlugin(QuantumDbPluginV2):
    supported_extension_aliases = ['udp-channels', 'port-metadata']

    def __init__(self):
        db.configure_db({'sql_connection': configuration.DB_SQL_CONNECTION,
                         'base': models_v2.model_base.BASEV2})

    def create_network(self, context, network, **kwargs):
        session = context.session
        with session.begin(subtransactions=True):
            new_network = super(UdpSocketPlugin, self).create_network(
                context, network, **kwargs)
            LOG.debug(new_network)
            plugin_db.allocate_udp_link(session, new_network['id'])
            return new_network

    def delete_network(self, context, id):
        session = context.session
        with session.begin(subtransactions=True):
            plugin_db.deallocate_udp_link(session, id)
            super(UdpSocketPlugin, self).delete_network(context, id)

    def create_port(self, context, port):
        session = context.session
        with session.begin(subtransactions=True):
            new_port = super(UdpSocketPlugin, self).create_port(
                context, port)
            plugin_db.allocate_udp_for_port(
                session, new_port['network_id'], new_port['id'])
            return new_port

    def delete_port(self, context, id):
        port = self._get_port(context, id)
        session = context.session
        with session.begin(subtransactions=True):
            new_port = super(UdpSocketPlugin, self).delete_port(context, id)
            plugin_db.deallocate_udp_for_port(
                session, port.network_id, port.id)
            return new_port

    def get_udp_port(self, tenant_id, network_id, port_id):
        session = db.get_session()
        return plugin_db.get_udp_for_port(session, network_id, port_id)

    def get_port_attrs(self, tenant_id, network_id, port_id):
        session = db.get_session()
        return plugin_db.get_attrs_for_port(session, port_id)

    def set_port_attrs(self, tenant_id, network_id, port_id, metadata):
        session = db.get_session()
        return plugin_db.set_attrs_for_port(session, port_id, metadata)
