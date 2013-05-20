import random
import subprocess
import re
import os

import psutil

from nova import flags, exception, db
from nova.openstack.common import log as logging
from nova.openstack.common import cfg
from nova.virt import images
from nova.virt.driver import ComputeDriver
from nova.virt.libvirt.driver import LibvirtDriver
from nova.compute import instance_types
from nova.compute import power_state
from nova import utils
from nova.utils import ensure_tree, execute
from dynagen import dynamips_lib
from dynagen.dynamips_lib import NIO_udp

from ermak.compute.vif import add_alias, delete_alias, list_addresses
from ermak.util.dynamips import DynamipsClient

LOG = logging.getLogger("nova.virt.dynamips")
dynamips_lib.debug = LOG.debug

MB = 1024 * 1024
GB = MB * 1024

dynamips_opts = [
    cfg.StrOpt('dynamips_host',
               default='localhost',
               help='Connection host for dynamips'),
    cfg.StrOpt('dynamips_port',
               default=7200,
               help='Connection port for dynamips')]
FLAGS = flags.FLAGS
flags.DECLARE('vncserver_proxyclient_address', 'nova.vnc')
FLAGS.register_opts(dynamips_opts)


def _get_image_meta(context, image_ref):
    image_service, image_id = glance.get_remote_image_service(context,
        image_ref)
    return image_service.show(context, image_id)


def get_connection(read_only=False):
    return DynamipsDriver(read_only)


def is_port_free(port):
    # netcat will exit with 0 only if the port is in use,
    # so a nonzero return value implies it is unused
    cmd = 'netcat', 'localhost', port, '-z'
    try:
        stdout, stderr = execute(*cmd)
        return False
    except exception.ProcessExecutionError:
        return True


class PortPool(object):

    def __init__(self, start_port, end_port):
        self._ports = {}
        self._leases = {}
        self._start_port = start_port
        self._end_port = end_port

    @utils.synchronized('tcp_port_allocate')
    def acquire(self, lease):
        port = self._leases.get(lease)
        if port and not is_port_free(port):
            return port
        else:
            self.release(lease)
        for port in xrange(self._start_port, self._end_port):
            if port not in self._ports and is_port_free(port):
                self._ports[port] = lease
                self._leases[lease] = port
                return port
        raise Exception("Can not find free port to bind")

    def release(self, lease):
        port = self._leases.get(lease)
        if port:
            del self._leases[lease]
            del self._ports[port]


class RouterWrapper(object):
    """
    Mixin for Router class with openstack conversions
    """

    STATES = {
        'stopped': power_state.SHUTDOWN,
        'running': power_state.RUNNING,
        'suspended': power_state.SUSPENDED
    }

    @property
    def os_state(self):
        return self.STATES[self.state]

    @property
    def os_name(self):
        return self.__os_name

    @os_name.setter
    def os_name(self, value):
        self.__os_name = value

    @property
    def os_prototype(self):
        return self.__os_prototype

    @os_prototype.setter
    def os_prototype(self, instance):
        self.__os_prototype = instance

    def start_ajaxterm(self, port):
        if is_port_free(port):
            args = ["ajaxterm",
                    "-p", str(port),  # TODO: config host too
                    # "-d",
                    "--command", "telnet -E localhost %s" % self.console]
            LOG.debug("Spawning process: %s" % args)
            if getattr(self, '_ajaxterm_process', None):
                self._ajaxterm_process.kill()
            self._ajaxterm_process = subprocess.Popen(args)
        return FLAGS.vncserver_proxyclient_address, port

    def stop_ajaxterm(self):
        LOG.debug("About to kill ajaxterm process")
        if getattr(self, '_ajaxterm_process', None):
            LOG.debug("Killing ajaxterm process")
            self._ajaxterm_process.kill()


class DynamipsDriver(ComputeDriver):
    """Driver for Dynamips CISCO emulator."""

    def __init__(self, read_only=False):
        super(DynamipsDriver, self).__init__()
        self._routers = {}
        self.dynamips = DynamipsClient(
            FLAGS.dynamips_host, FLAGS.dynamips_port)
        start_port, end_port = FLAGS.ajaxterm_portrange.split("-")
        start_port, end_port = int(start_port), int(end_port)
        self._port_pool = PortPool(start_port, end_port)

    def init_host(self, host):
        pass

    def legacy_nwinfo(self):
        return False

    def get_info(self, instance):
        n = self._router_by_name(instance["name"])
        mem_mb = instance_types.get_instance_type(
            n.os_prototype['instance_type_id']).get("memory_mb")
        return {
            'state': n.os_state,
            'max_mem': int(mem_mb) * 1024,
            'mem': n.ram * 1024,
            'num_cpu': 1,
            'cpu_time': 0  # cpuinfo?
        }

    def _router_by_name(self, name):
        try:
            return filter(lambda r: r.os_name == name,
                          self._routers.itervalues())[0]
        except IndexError:
            raise exception.InstanceNotFound(instance_id=name)

    def list_instances(self):
        """Lists instances

        :return list of names
        """
        return map(lambda x: x.os_name, self._routers.itervalues())

    def _class_for_platform(self, platform):
        try:
            # try direct model first
            return dynamips_lib.__dict__[platform.upper()]
        except KeyError:
            raise exception.FlavorNotFound(
                "Can not find router platform %s" % platform)

    def _chassis_for_flavor(self, flavorname):
        res = re.match(r'c1\.(.*)', flavorname)
        if res:
            return res.group(1)
        else:
            raise exception.FlavorNotFound(
                "Dynamips accepts only c1.xxx flavors, got %s" % flavorname)

    def _class_for_instance(self, image_meta):
        class_ = self._class_for_platform(
            image_meta['properties']['dynamips_platform'])
        class CurrentRouter(RouterWrapper, class_):  # TODO: metaclass?
            pass
        return CurrentRouter

    def _instance_to_router(self, context, instance, image_meta):
        inst_type = \
            instance_types.get_instance_type(instance["instance_type_id"])
        chassis = self._chassis_for_flavor(inst_type['name'])
        C = self._class_for_instance(image_meta)
        r = C(self.dynamips, name=instance["id"], chassis=chassis)
        r.os_name = instance["name"]
        r.ram = inst_type["memory_mb"]
        r.os_prototype = instance
        return r

    def _setup_image(self, context, instance):
        base_dir = os.path.join(FLAGS.instances_path, FLAGS.base_dir_name)
        if not os.path.exists(base_dir):
            ensure_tree(base_dir)
        path = os.path.abspath(os.path.join(base_dir, instance["image_ref"]))
        if not os.path.exists(path):
            images.fetch_to_raw(
                context, instance["image_ref"], path,
                instance["user_id"], instance["project_id"])
        return path


    def _mklabel(self, ip):
        return "%02x%02x%02x%02x" % tuple(map(int, ip.split('.')))

    def _withmask(self, addr, prefix):
        return str(addr) + '/' + str(prefix)

    @utils.synchronized('udp_channel_setup')
    def _setup_network(self, context, router, instance, network_info):
        for vif in network_info:
            iface = FLAGS.data_iface
            udp_attrs = vif['meta']['quantum_udp_attrs']
            port_attrs = vif['meta']['quantum_port_attrs']
            on_same_machine = udp_attrs['dst-address'] in list_addresses(iface)
            LOG.debug("UDP attrs are %s, addresses are %s, on_same_machine is %s" % (udp_attrs, list_addresses(iface), on_same_machine))

            add_alias(
                iface,
                self._withmask(
                    udp_attrs['src-address'], udp_attrs['prefix-len']),
                label=self._mklabel(udp_attrs['src-address']))
            if on_same_machine:
                delete_alias(
                    iface,
                    self._withmask(
                        udp_attrs['dst-address'], udp_attrs['prefix-len']),
                    label=self._mklabel(udp_attrs['dst-address']))
            adapter = router.slot[port_attrs['slot-id']]
            if not adapter:
                model = port_attrs['slot-model']
                if model:
                    class_ = getattr(dynamips_lib, model.replace('-', '_'))
                    adapter = class_(router, port_attrs['slot-id'])
                    router.slot[port_attrs['slot-id']] = adapter
                else:
                    LOG.error("Errant vif: %s" % vif)
                    raise Exception("Expected slot model to be defined")
            LOG.debug("Creating nio to %s, addresses are %s" % (udp_attrs['dst-address'], list_addresses(iface)))
            nio = NIO_udp(
                self.dynamips,
                udp_attrs['src-port'],
                udp_attrs['dst-address'],
                udp_attrs['dst-port'],
                adapter=adapter,
                port=port_attrs['port-id'])
            adapter.nio(port_attrs['port-id'], nio)
            if on_same_machine:
                add_alias(
                    iface,
                    self._withmask(
                        udp_attrs['dst-address'], udp_attrs['prefix-len']),
                    label=self._mklabel(udp_attrs['dst-address']))

    @utils.synchronized('udp_channel_setup')
    def _tear_down_network(self, router, instance, network_info):
        for vif in network_info:
            try:
                iface = FLAGS.data_iface
                udp_attrs = vif['meta']['quantum_udp_attrs']
                port_attrs = vif['meta']['quantum_port_attrs']
                adapter = router.slot[port_attrs['slot-id']]
                (dynint, dynport) = nio.interfaces_mips2dyn[port_attrs['port-id']]
                adapter.disconnect(dynint, dynport)
                adapter.delete_nio(dynint, dynport)
                delete_alias(
                    iface,
                    self._withmask(
                        udp_attrs['src-address'], udp_attrs['prefix-len']),
                    label=self._mklabel(udp_attrs['src-address']))
            except Exception as e:
                LOG.error("Can not deallocate vif %s" % vif, e)

    def _do_create_instance(self, context, instance, image_meta, network_info):
        image = self._setup_image(context, instance)
        r = self._instance_to_router(context, instance, image_meta)
        self._setup_network(context, r, instance, network_info)
        r.image = image
        r.mmap = False
        self._routers[instance["id"]] = r

    def spawn(self, context, instance, image_meta, injected_files,
              admin_password, network_info=[], block_device_info=None):
        self._do_create_instance(context, instance, image_meta, network_info)
        self._router_by_name(instance["name"]).start()

    def destroy(self, instance, network_info, block_device_info=None):
        try:
            r = self._router_by_name(instance["name"])
        except exception.NotFound:
            r = None

        if r is not None:
            r.stop_ajaxterm()
            r.stop()  # TODO: error "unable to stop instance" may occur
            self._tear_down_network(r, instance, network_info)
            r.delete()
            del self._routers[r.name]
            # TODO: remove IOS image (?)
            # TODO: remove ramdisks (?)

    def reboot(self, instance, network_info, reboot_type,
               block_device_info=None):
        r = self._routers[instance["id"]]
        r.stop_ajaxterm()
        r.stop()
        r.start()

    # get_console_pool_info

    def get_console_output(self, instance):
        # TODO: dunno
        raise NotImplementedError()

    def get_vnc_console(self, instance):
        raise NotImplementedError("Use get_web_console instead")

    @exception.wrap_exception()
    def get_web_console(self, instance):
        """Get host and port for TELNET console on instance

        Desperate its name, VNC console infrastructure is suitable for
        any protocols, including SSH and TELNET.
        """
        LOG.debug("Available instance ids are: %s" % self._routers.keys())
        r = self._routers[instance["id"]]
        port = self._port_pool.acquire(instance["id"])
        host, port = r.start_ajaxterm(port)
        return {'host': host, 'port': port, 'internal_access_path': None}

    # get_diagnostics
    # get_all_bw_usage

    def get_host_ip_addr(self):
        """
        Retrieves the IP address of the dom0
        """
        # no meaning in our implementation
        raise NotImplementedError()

    # snapshot

    # compare_cpu
    # migrate_disk_and_power_off
    # finish_migration
    # confim_migration
    # finish_revert_migration

    def pause(self, instance):
        """Pause the specified instance."""
        return self.suspend(instance)

    def unpause(self, instance):
        """Unpause paused VM instance"""
        return self.resume(instance)

    def suspend(self, instance):
        """suspend the specified instance"""
        self._routers[instance["id"]].suspend()

    def resume(self, instance):
        """resume the specified instance"""
        r = self._router_by_name(instance["name"])
        if r.os_state != power_state.RUNNING:
            r.resume()

    def _current_state_for_instance(self, instance):
        try:
            return self._router_by_name(instance["name"]).os_state
        except exception.NotFound:
            return power_state.NOSTATE

    def resume_state_on_host_boot(self, context, instance, network_info,
                                  block_device_info=None):
        """resume guest state when a host is booted"""
        current_state = self._current_state_for_instance(instance)
        image_meta = _get_image_meta(context, instance['image_ref'])
        if current_state == power_state.NOSTATE:
            self._do_create_instance(context, instance, image_meta, network_info)
        current_state = self._current_state_for_instance(instance)

        if current_state == power_state.SHUTDOWN:
            self.power_on(instance)
            return self._current_state_for_instance(instance)
        else:
            return power_state.SHUTDOWN

    # rescue
    # unrescue

    def power_off(self, instance):
        """Power off the specified instance."""
        r = self._routers[instance["id"]]
        r.stop_ajaxterm()
        r.stop()  # TODO: semantics may differ

    def power_on(self, instance):
        """Power on the specified instance"""
        self._routers[instance["id"]].start()  # TODO: semantics may differ

    def _gen_stats(self):
        """Return currently known host stats"""
        disk_usage = psutil.disk_usage('/')
        local_gb = disk_usage.total / GB
        local_gb_used = disk_usage.used / GB
        disk_available_least = disk_usage.free / GB

        mem_usage = psutil.virtual_memory()
        memory_mb = mem_usage.total / MB
        memory_mb_used = mem_usage.used / MB

        # list of (arch, hypervisor_type, vm_mode)
        capabilities = [
            ('ppc', 'dynamips', 'ios')
        ]

        return {
            'vcpus': LibvirtDriver.get_vcpu_total(),
            'vcpus_used': self.get_vcpu_used(),
            'cpu_info': '{}',
            'disk_total': disk_usage.total,
            'disk_used': disk_usage.used,
            'disk_available': disk_usage.free,
            'host_memory_total': mem_usage.total,
            'host_memory_free': mem_usage.free,

            'memory_mb': memory_mb,
            'memory_mb_used': memory_mb_used,
            'local_gb': local_gb,
            'local_gb_used': local_gb_used,
            'disk_available_least': disk_available_least,

            'hypervisor_type': 'dynamips',
            'hypervisor_version': '0.2.7+',
            'hypervisor_hostname': '',
            'supported_instances': capabilities}

    def get_available_resource(self):
        return self._gen_stats()

    def get_host_stats(self, refresh=False):
        return self._gen_stats()

    def get_vcpu_used(self):
        return sum(
            map(lambda r: int(r.state == 'running'),
                self._routers.values()))

    # refresh_security_group_rules
    # refresh_security_group_members
    # refresh_provider_fw_rules

    def reset_network(self, instance):
        """reset networking for specified instance"""
        pass

    # set_admin_password

    # inject_file

    # agent_update
    # inject_network_info

    def poll_rebooting_instances(self, timeout):
        """Poll for rebooting instances"""
        # TODO: make list?
        raise NotImplementedError()

    def poll_rescued_instances(self, timeout):
        """Poll for rescued instances"""
        # TODO: wtf is rescue?
        raise NotImplementedError()

    def host_power_action(self, host, action):
        """Reboots, shuts down or powers up the host."""
        # TODO: wtf
        raise NotImplementedError()

    # host_maintenance_mode
    # set_host_enabled

    def plug_vifs(self, instance, network_info):
        """Plug VIFs into networks."""
        pass

    def unplug_vifs(self, instance, network_info):
        """Unplug VIFs from networks."""
        pass

    def update_host_status(self):
        """Refresh host stats"""
        # TODO: wtf
        raise NotImplementedError()

    # list_disks

    def list_interfaces(self, instance_name):
        """
        Return the IDs of all the virtual network interfaces attached to the
        specified instance, as a list.  These IDs are opaque to the caller
        (they are only useful for giving back to this layer as a parameter to
        interface_stats).  These IDs only need to be unique for a given
        instance.

        Note that this function takes an instance ID.
        """
        # TODO: cXXXX show_hardware (?)
        raise NotImplementedError()

    # interface_stats

    def manage_image_cache(self, context):
        """
        Manage the driver's local image cache.

        Some drivers chose to cache images for instances on disk. This method
        is an opportunity to do management of that cache which isn't directly
        related to other calls into the driver. The prime example is to clean
        the cache and remove images which are no longer of interest.
        """
        # TODO: implement
        pass

    # add_to_aggregate
    # remove_from_aggregate
