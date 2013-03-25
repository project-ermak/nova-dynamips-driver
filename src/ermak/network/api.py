from nova.openstack.common import log as logging
from nova import flags
from nova.network import quantumv2
from nova.network.quantumv2.api import API
from quantumclient.v2_0.client import Client, APIParamsCall


LOG = logging.getLogger("nova.network.api")
FLAGS = flags.FLAGS


class QuantumUdpClient(Client):

    channels_path = "/extensions/udp/tenants/%s/networks/%s/channels"
    channel_path = \
        "/extensions/udp/tenants/%s/networks/%s/channels/%s"

    attr_path = "/extensions/attributes/tenants/%s" + \
                "/networks/%s/networks/%s/ports/%s"

    def __init__(self, *args, **kwargs):
        super(QuantumUdpClient, self).__init__(*args, **kwargs)

    @APIParamsCall
    def list_channels(self, tenant, net_id, **params):
        return self.get(self.channels_path % (tenant, net_id),
            params=params)

    @APIParamsCall
    def show_channel(self, tenant, net_id, port_id, **params):
        return self.get(self.channel_path % (tenant, net_id, port_id),
            params=params)

    @APIParamsCall
    def show_port_attrs(self, tenant, net_id, port_id, **params):
        return self.get(self.attr_path% (tenant, net_id, port_id),
            params=params)

    @APIParamsCall
    def set_port_attrs(self, tenant, net_id, port_id, attributes):
        body = {
            'port': {
                'port-id': port_id,
                'attributes': attributes
            }
        }
        return self.put(self.attr_path % (tenant, net_id, port_id), body=body)


class QuantumUdpApi(API):

    def __init__(self, *args, **kwargs):
        super(API, self).__init__(*args, **kwargs)

    def ext_client(self):
        return QuantumUdpClient(
            FLAGS.quantum_connection_host,
            FLAGS.quantum_connection_port,
            format="json",
            logger=LOG)

    def _get_udp_info(self, tenant_id, net_id, port_id):
        """
        :return: Unmodified dict from plugin. Expected to have keys:
                - src-address
                - src-port
                - dst-address
                - dst-port
                - id
        """
        channel = \
            self.ext_client().show_channel(tenant_id, net_id, port_id)
        return channel['channel']

    def _get_port_attrs(self, tenant_id, net_id, port_id):
        """
        :return: Unmodified dict from plugin. Expected to have keys:
                - slot-id
                - port-id
        """
        channel = self.ext_client().show_port_attrs(
            tenant_id, net_id, port_id)
        return channel['port']['attributes']

    def _get_port_id_by_attachment(self, context, net_id, attachment):
        client = quantumv2.get_client(context)
        for port in client.list_ports(net_id)['ports']: # TODO: filtering
            att = client.show_port_attachment(net_id, port['port']['id'])
            if att['attachment'].get('id') == attachment:
                return port['port']['id']
        raise AssertionError(
            "Can not find port in network %s with attachment %s" %
            (net_id, attachment))

    def _build_network_info_model(self, context, instance, networks=None):
        nw_info = super(QuantumUdpApi, self)._build_network_info_model(
            context, instance, networks)
        networks = networks or []
        LOG.debug("Got networks: %s" % networks)
        LOG.debug("Got nw_info: %s" % nw_info)
        networks_dict = dict(map(lambda n: (n['network_id'], n), networks))
        for vif in nw_info:
            network = networks_dict[vif['id']]
            net_tenant_id = network['net_tenant_id']
            quantum_net_id = network['quantum_net_id']
            attachment = vif['id']
            port_id = self._get_port_id_by_attachment(context,
                quantum_net_id, attachment)
            specific_args = {
                'quantum_net_id': network['quantum_net_id'],
                'quantum_udp_port_info':
                    self._get_udp_info(net_tenant_id, quantum_net_id, port_id),
                'quantum_port_attrs':
                    self._get_port_attrs(
                        net_tenant_id, quantum_net_id, port_id)}
            vif['meta'].update(specific_args)
        return nw_info