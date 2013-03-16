from nova.openstack.common import cfg
from nova import db
from nova import flags
from nova import exception
from nova import logging
from nova import utils
from nova.virt import vif


linux_net_opts = [
    cfg.StrOpt('data_iface',
        default='eth0',
        help='interface for UDP channel VIF'),
]
FLAGS = flags.FLAGS
FLAGS.register_opts(linux_net_opts)

LOG = logging.getLogger("nova.virt.vif")


class QuantumUdpChannelVIFDriver(vif.VIFDriver):

    # 2013-03-16 17:33:11 DEBUG nova.compute.manager [req-783a00bf-dabf-46a5-bcec-7401b14504c2 190b0d2081dc40dd926d96bafb870c36 9277f1a0ce1d4911bcd80121d8186bc9] [instance: 8db661dc-53ba-4316-bfe0-09f66816b80b] Instance network_info: |[VIF({'network': Network({'bridge': u'br100', 'subnets': [Subnet({'ips': [FixedIP({'meta': {}, 'version': 4, 'type': u'fixed', 'floating_ips': [], 'address': u'192.168.1.2'})], 'version': 4, 'meta': {u'dhcp_server': u'192.168.1.1'}, 'dns': [IP({'meta': {}, 'version': 4, 'type': u'dns', 'address': u'8.8.4.4'})], 'routes': [], 'cidr': u'192.168.1.0/24', 'gateway': IP({'meta': {}, 'version': 4, 'type': u'gateway', 'address': u'192.168.1.1'})}), Subnet({'ips': [], 'version': None, 'meta': {u'dhcp_server': None}, 'dns': [], 'routes': [], 'cidr': None, 'gateway': IP({'meta': {}, 'version': None, 'type': u'gateway', 'address': None})})], 'meta': {u'tenant_id': None, u'should_create_bridge': True, u'bridge_interface': u'eth0'}, 'id': u'e1b7c30e-46d8-4f8f-b4f0-548ebc9ef8e7', 'label': u'linhome-network'}), 'meta': {}, 'id': u'5f87d463-1a28-48bd-8277-4fc20c42f98d', 'address': u'fa:16:3e:23:95:64'})]| from (pid=8773) _allocate_network /usr/lib/python2.7/dist-packages/nova/compute/manager.py:572

    def plug(self, instance, network, mapping):
        iface = FLAGS.data_iface
        port_info = self._get_port_by_uuid(mapping['uuid'])
        cidr = ''
        try:
            utils.execute('ip', 'addr', 'add',
                          'dev', iface,
                           cidr, run_as_root=True)
        except exception.ProcessExecutionError:
            LOG.warning(_("Failed while pluggin vif of instance '%s'"),
                instance['name'])
        result = {
            'mac_address': mapping['mac'],
            'src_address': '',
            'src_port': '',
            'dst_address': '',
            'dst_port': ''}
        return result

    def unplug(self, instance, network, mapping):
        iface = FLAGS.data_iface
        cidr = ''
        try:
            utils.execute('ip', 'addr', 'delete',
                          'dev', iface,
                          cidr, run_as_root=True)
        except exception.ProcessExecutionError:
            LOG.warning(_("Failed while unplugging vif of instance '%s'"),
                instance['name'])
            raise