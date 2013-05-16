from lxml import etree
from nova.openstack.common import cfg
from nova import flags
from nova import exception
from nova.openstack.common import log as logging
from nova import utils
from nova.virt import vif

from netifaces import ifaddresses, AF_INET
from nova.virt.libvirt.config import LibvirtConfigGuestDevice


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


class LibvirtConfigUdpInterface(LibvirtConfigGuestDevice):

    def __init__(self, **kwargs):
        super(LibvirtConfigGuestDevice, self).__init__(
            root_name="interface",
            **kwargs)

        self.model = None
        self.mac_addr = None
        self.src_address = None
        self.src_port= None
        self.dst_address = None
        self.dst_port = None

    def format_dom(self):
        dev = super(LibvirtConfigGuestDevice, self).format_dom()

        dev.set("type", "udp")
        dev.append(etree.Element("mac", address=self.mac_addr))
        if self.model:
            dev.append(etree.Element("model", type=self.model))
        dev.append(etree.Element("source",
            address=self.src_address,
            port=self.src_port))
        dev.append(etree.Element("destination",
            address=self.dst_address,
            port=self.dst_port))
        return dev


class LibvirtQuantumUdpChannelVIFDriver(vif.VIFDriver):

    def _get_config(self, mapping, udp_attrs):
        conf = LibvirtConfigUdpInterface()
        conf.net_type = 'udp'
        conf.mac_addr = mapping['mac']
        conf.src_address = udp_attrs['src_address']
        conf.src_port = udp_attrs['src_port']
        conf.dst_address = udp_attrs['dst_address']
        conf.dst_port = udp_attrs['dst_port']
        return conf

    @utils.synchronized('udp_channel_setup')
    def plug(self, instance, vif, **kwargs):
        LOG.debug("VIFDriver got vif: %s" % vif)
        iface = FLAGS.data_iface
        network, mapping = vif
        udp_attrs = network['meta']['quantum_udp_udp_attrs']
        add_alias(iface, udp_attrs['src-address'])
        return self._get_config(mapping, udp_attrs)

    @utils.synchronized('udp_channel_setup')
    def unplug(self, instance, vif, **kwargs):
        iface = FLAGS.data_iface
        # TODO: no info here when deleting :(
        udp_attrs = vif['meta']['quantum_udp_udp_attrs']
        delete_alias(iface, udp_attrs['src-address'])
