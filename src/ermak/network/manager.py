from nova import log as logging
from nova import flags
from nova.network.quantum.client import api_call, Client
from nova.network.quantum.manager import QuantumManager


LOG = logging.getLogger(__name__)
FLAGS = flags.FLAGS


class QuantumUdpClient(Client):

    action_prefix = '/v1.1/'

    networks_path = "/tenants/{tenant_id}/networks"
    network_path = "/tenants/{tenant_id}/networks/%s"
    ports_path = "/tenants/{tenant_id}/networks/%s/ports"
    port_path = "/tenants/{tenant_id}/networks/%s/ports/%s"
    attachment_path = "/tenants/{tenant_id}/networks/%s/ports/%s/attachment"

    channels_path = "/extensions/udp/tenants/{tenant_id}/networks/%s/channels"
    channel_path = \
        "/extensions/udp/tenants/{tenant_id}/networks/%s/channels/%s"

    def __init__(self, *args, **kwargs):
        super(QuantumUdpClient, self).__init__(*args, **kwargs)

    @api_call
    def list_channels(self, net_id, filter_ops=None):
        return self.do_request("GET", self.channels_path % net_id,
            params=filter_ops)

    @api_call
    def show_channel(self, net_id, port_id, filter_ops=None):
        return self.do_request("GET", self.channel_path % (net_id, port_id),
            params=filter_ops)


class QuantumUdpManager(QuantumManager):

    def __init__(self, *args, **kwargs):
        super(QuantumUdpManager, self).__init__(*args, **kwargs)
        self.ext_conn = QuantumUdpClient(
            FLAGS.quantum_connection_host,
            FLAGS.quantum_connection_port,
            format="json",
            logger=LOG)

    def _get_udp_info(self, tenant_id, net_id, port_id):
        """
        :return Unmodified dict from plugin. Expected to have keys:
                - src_address
                - src_port
                - dst_address
                - dst_port
        """
        channel = self.ext_conn.show_channel(net_id, port_id, tenant=tenant_id)
        return channel['channel']

    def _get_port_id_by_attachment(self, net_id, attachment):
        client = self.q_conn.client
        for port in client.list_ports(net_id)['ports']:
            att = client.show_port_attachment(net_id, port['port']['id'])
            if att['attachment'].get('id') == attachment:
                return port['port']['id']
        raise AssertionError(
            "Can not find port in network %s with attachment %s" %
            (net_id, attachment))

    def build_network_info_model(self, context, vifs, networks,
                                 rxtx_factor, instance_host):
        nw_info = super(QuantumUdpManager, self).build_network_info_model(
            context, vifs, networks, rxtx_factor, instance_host)
        for vif in nw_info:
            network = networks[vif['id']]
            net_tenant_id = network['net_tenant_id']
            quantum_net_id = network['quantum_net_id']
            attachment = vif['id']
            port_id = self._get_port_id_by_attachment(
                quantum_net_id, attachment)
            specific_args = {
                'quantum_net_id': network['quantum_net_id'],
                'quantum_udp_port_info':
                    self._get_udp_info(net_tenant_id, quantum_net_id, port_id)
            }
            vif.set_meta(specific_args)
        return nw_info