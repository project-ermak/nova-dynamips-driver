from nova.openstack.common import cfg
from nova import flags
from nova import exception
from nova.openstack.common import log as logging
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

    def plug(self, instance, vif, **kwargs):
        iface = FLAGS.data_iface
        port_info = vif['meta']['quantum_udp_port_info']
        port_attrs = vif['meta']['quantum_port_attrs']
        try:
            utils.execute('ip', 'addr', 'add',
                          'dev', iface,
                           port_info['src-address'], run_as_root=True)
        except exception.ProcessExecutionError:
            LOG.warning(_("Failed while pluggin vif of instance '%s'"),
                instance['name'])
        result = {
            'mac_address': vif['address'],
            'src_address': port_info['src-address'],
            'src_port': port_info['src-port'],
            'dst_address': port_info['dst-address'],
            'dst_port': port_info['dst-port'],
            'slot_id': port_attrs['slot-id'],
            'port_id': port_attrs['port-id']}
        return result

    def unplug(self, instance, vif, **kwargs):
        iface = FLAGS.data_iface
        # TODO: no info here when deleting :(
        port_info = vif['meta']['quantum_udp_port_info']
        try:
            utils.execute('ip', 'addr', 'delete',
                          'dev', iface,
                          port_info['src-address'], run_as_root=True)
        except exception.ProcessExecutionError:
            LOG.warning(_("Failed while unplugging vif of instance '%s'"),
                instance['name'])
            raise
