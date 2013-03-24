import logging
import json

from quantum import wsgi
from quantum.api import faults
from quantum.common import exceptions as qexception
from quantum.extensions import extensions
from quantum.manager import QuantumManager
from quantum.const import UUID, PORT_ID


LOG = logging.getLogger("quantum.api.portstats")


class Portmetadata(object):
    def __init__(self):
        pass

    @classmethod
    def get_name(cls):
        return "Port metadata"

    @classmethod
    def get_alias(cls):
        return "port-metadata"

    @classmethod
    def get_description(cls):
        return "Port metadata provider"

    @classmethod
    def get_namespace(cls):
        return "http://docs.openstack.org/ext/port-metadata/api/v1.0"

    @classmethod
    def get_updated(cls):
        return "2013-03-24-T00:00:00-00:00"

    @classmethod
    def get_resources(cls):
        controller = PortsMetadataController(QuantumManager.get_plugin())
        parent_resource = dict(member_name="network",
            collection_name="extensions/metadata/tenants/" +\
                            ":(tenant_id)/networks")
        return [extensions.ResourceExtension('ports', controller,
            parent=parent_resource)]


class PortsMetadataController(wsgi.Controller):

    def __init__(self, plugin):
        self._plugin = plugin

    def _port_view(self, request, tenant_id, network_id, port_id):
        """Returns udp port info for a given port"""
        if not hasattr(self._plugin, "get_port_attrs"):
            return faults.Quantum11HTTPError(
                qexception.NotImplementedError("get_port_attrs"))
        meta = self._plugin.get_port_attrs(
            tenant_id, network_id, port_id)
        return {'attributes': meta, PORT_ID: port_id}

    def index(self, request, tenant_id, network_id):
        ports = self._plugin.get_all_ports(tenant_id, network_id)
        def view(port):
            return self._port_view(
                request, tenant_id, network_id, port[PORT_ID])
        result = map(view, ports)
        return {'ports': result}

    def show(self, request, tenant_id, network_id, id):
        port = self._plugin.get_port_details(tenant_id, network_id, id)
        port_viewmodel = self._port_view(
            request, tenant_id, network_id, port[PORT_ID])
        return {'port': port_viewmodel}

    def update(self, request, tenant_id, network_id, id):
        payload = json.loads(request.body)
        meta = payload['port']['attributes']
        print meta
        self._plugin.set_port_attrs(tenant_id, network_id, id, meta)
        updated_data = self._port_view(request, tenant_id, network_id, id)
        return {'port': updated_data}


