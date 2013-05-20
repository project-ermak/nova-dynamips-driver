from nova.network.quantumv2 import _get_auth_token
from nova.openstack.common import log as logging
from nova import flags, exception
from nova.network import quantumv2
from nova.network.quantumv2.api import API, _ensure_requested_network_ordering

from ermak.udpclient import QuantumUdpClient


LOG = logging.getLogger("nova.network.api")
FLAGS = flags.FLAGS


class QuantumUdpApi(API):

    def __init__(self, *args, **kwargs):
        super(API, self).__init__(*args, **kwargs)

    def ext_client(self, context):
        token = context.auth_token
        if not token:
            if FLAGS.quantum_auth_strategy:
                token = _get_auth_token()
        if token:
            my_client = QuantumUdpClient(
                endpoint_url=FLAGS.quantum_url,
                token=token, timeout=FLAGS.quantum_url_timeout)
        else:
            my_client = QuantumUdpClient(
                endpoint_url=FLAGS.quantum_url,
                auth_strategy=None, timeout=FLAGS.quantum_url_timeout)
        return my_client

    def _get_udp_info(self, context, tenant_id, net_id, port_id):
        """
        :return: Unmodified dict from plugin. Expected to have keys:
                - src-address
                - src-port
                - dst-address
                - dst-port
                - id
        """
        channel = \
            self.ext_client(context).show_channel(tenant_id, net_id, port_id)
        return channel['channel']

    def _get_port_attrs(self, context, tenant_id, net_id, port_id):
        """
        :return: Unmodified dict from plugin. Expected to have keys:
                - slot-id
                - port-id
                - slot-model
        """
        channel = self.ext_client(context).show_port_attrs(
            tenant_id, net_id, port_id)
        return channel['port']['attributes']

    def _get_port_id_by_instance(self, context, net_id, instance_id):
        client = quantumv2.get_client(context)
        ports = client.list_ports()['ports']
        LOG.debug("Got ports: %s" % ports)
        for port in ports: # TODO: server-side filtering
            att = client.show_port(port['id'])['port']
            LOG.debug("Got port: %s" % ports)
            if att['device_id'] == instance_id and att['network_id'] == net_id:
                return port['id']
        raise AssertionError(
            "Can not find port in network %s with device_id %s" % (
                net_id, instance_id))

    def _build_network_info_model(self, context, instance, networks=None):
        nw_info = super(QuantumUdpApi, self)._build_network_info_model(
            context, instance, networks)
        networks = networks or []
        LOG.debug("Got networks: %s" % networks)
        LOG.debug("Got nw_info: %s" % nw_info)
        networks_dict = dict(map(lambda n: (n['id'], n), networks))
        for vif in nw_info:
            network = networks_dict.get(vif['network']['id'])
            if not network:
                continue
            net_tenant_id = network['tenant_id']
            quantum_net_id = network['id']
            port_id = self._get_port_id_by_instance(context,
                quantum_net_id, instance['uuid'])
            udp_info = self._get_udp_info(
                context, net_tenant_id, quantum_net_id, port_id)
            port_attrs = self._get_port_attrs(
                context, net_tenant_id, quantum_net_id, port_id)
            specific_args = {
                'quantum_net_id': quantum_net_id,
                'quantum_udp_attrs': udp_info,
                'quantum_port_attrs': port_attrs}
            vif['meta'].update(specific_args)
        return nw_info

    def _get_available_networks(self, context, project_id,
                                net_ids=None):
        """Return only specified networks if provided.

        Standard implementation uses public nets if empty list
        provided, this is not desirable behavior."""
        if net_ids is None:
            return super(QuantumUdpApi, self)._get_available_networks(
                context, project_id)
        elif not net_ids:
            return []

        # If user has specified to attach instance only to specific
        # networks, add them to **search_opts
        quantum = quantumv2.get_client(context)
        search_opts = {"tenant_id": project_id, 'shared': False, 'id': net_ids}
        nets = quantum.list_networks(**search_opts).get('networks', [])
        found_nets = map(lambda x: x['id'], nets)
        if len(nets) != len(found_nets):
            set(net_ids).difference(found_nets)
            raise exception.NetworkNotFound(network_id=found_nets)

        _ensure_requested_network_ordering(lambda x: x['id'], nets, net_ids)
        LOG.debug("Nets for instance: %s" % nets)
        return nets


