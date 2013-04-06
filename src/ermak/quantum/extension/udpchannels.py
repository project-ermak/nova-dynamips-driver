import logging

from quantum import wsgi
from quantum.api import faults
from quantum.common import exceptions as qexception
from quantum.extensions import extensions
from quantum.manager import QuantumManager


LOG = logging.getLogger("quantum.api.portstats")


class Udpchannels(object):
    def __init__(self):
        pass

    @classmethod
    def get_name(cls):
        return "UDP channels"

    @classmethod
    def get_alias(cls):
        return "udp-channels"

    @classmethod
    def get_description(cls):
        return "Port info provider for UDP-based channels"

    @classmethod
    def get_namespace(cls):
        return "http://docs.openstack.org/ext/udp-ports/api/v1.0"

    @classmethod
    def get_updated(cls):
        return "2013-03-10-T00:00:00-00:00"

    @classmethod
    def get_resources(cls):
        controller = UdpChannelsController(QuantumManager.get_plugin())
        parent_resource = dict(member_name="network",
            collection_name="extensions/udp/tenants/" +\
                            ":(tenant_id)/networks")
        return [extensions.ResourceExtension('channels', controller,
            parent=parent_resource)]


class UdpChannelsController(wsgi.Controller):

    def __init__(self, plugin):
        self._resource_name = 'udp-port'
        self._plugin = plugin

    def _port_view(self, request, tenant_id, network_id, port_id):
        """Returns udp port info for a given port"""
        if not hasattr(self._plugin, "get_udp_port"):
            return faults.Quantum11HTTPError(
                qexception.NotImplementedError("get_udp_port"))
        udp_port = self._plugin.get_udp_port(tenant_id, network_id, port_id)
        return dict(udp_port)

    def index(self, request, tenant_id, network_id):
        ports = self._plugin.get_all_ports(tenant_id, network_id)
        def view(port):
            return self._port_view(
                request, tenant_id, network_id, port['id'])
        result = map(view, ports)
        return {'channels': result}

    def show(self, request, tenant_id, network_id, id):
        port_viewmodel = self._port_view(
            request, tenant_id, network_id, id)
        return {'channel': port_viewmodel}

