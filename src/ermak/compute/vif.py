from nova.openstack.common import cfg
from nova import flags
from nova import exception
from nova.openstack.common import log as logging
from nova import utils
from nova.virt import vif

from netifaces import ifaddresses, AF_INET


linux_net_opts = [
    cfg.StrOpt('data_iface',
               default='eth0',
               help='interface for UDP channel VIF'),
]
FLAGS = flags.FLAGS
FLAGS.register_opts(linux_net_opts)

LOG = logging.getLogger("nova.virt.vif")


def list_addresses(iface):
    addresses = ifaddresses(iface).get(AF_INET, [])
    return map(lambda x: x['addr'], addresses)

def add_alias(iface, address, label=None):
    """
        :param: address must be in format xx.xx.xx.xx/yy
        :param: label will be transformed in iface:label
    """
    try:
        cmdline = ['ip', 'addr', 'add', 'dev', iface, address]
        if label:
            cmdline.extend(['label', iface + ":" + label])
        utils.execute(*cmdline, run_as_root=True)
    except exception.ProcessExecutionError:
        LOG.warning(_(
            "Failed to set alias '%s' on interface '%s'"),
            (address, address))

def delete_alias(iface, address, label=None):
    try:
        cmdline = ['ip', 'addr', 'del', 'dev', iface, address]
        if label:
            cmdline.extend(['label', iface + ":" + label])
        utils.execute(*cmdline, run_as_root=True)
    except exception.ProcessExecutionError:
        LOG.warning(_(
            "Failed to unset alias '%s' on interface '%s'"),
            (address, address))


class QuantumUdpChannelVIFDriver(vif.VIFDriver):

    @utils.synchronized('udp_channel_setup')
    def plug(self, instance, vif, **kwargs):
        iface = FLAGS.data_iface
        udp_attrs = vif['meta']['quantum_udp_udp_attrs']
        port_attrs = vif['meta']['quantum_port_attrs']
        add_alias(iface, udp_attrs['src-address'])
        result = {
            'mac_address': vif['address'],
            'src_address': udp_attrs['src-address'],
            'src_port': udp_attrs['src-port'],
            'dst_address': udp_attrs['dst-address'],
            'dst_port': udp_attrs['dst-port'],
            'slot_id': port_attrs['slot-id'],
            'port_id': port_attrs['port-id']}
        return result

    @utils.synchronized('udp_channel_setup')
    def unplug(self, instance, vif, **kwargs):
        iface = FLAGS.data_iface
        # TODO: no info here when deleting :(
        udp_attrs = vif['meta']['quantum_udp_udp_attrs']
        delete_alias(iface, udp_attrs['src-address'])
