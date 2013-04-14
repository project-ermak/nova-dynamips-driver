import random
import re
import os

from nova import flags, exception, db
from nova.openstack.common import log as logging
from nova.openstack.common import cfg
from nova.virt import images
from nova.virt.driver import ComputeDriver
from nova.compute import instance_types
from nova.compute import power_state
from nova import utils
from nova.utils import ensure_tree, execute
from dynagen import dynamips_lib
from dynagen.dynamips_lib import NIO_udp

from ermak.compute.vif import QuantumUdpChannelVIFDriver
from ermak.compute.vif import add_alias, delete_alias, list_addresses
from ermak.util.dynamips import DynamipsClient

LOG = logging.getLogger("nova.virt.dynamips")
dynamips_lib.debug = LOG.debug

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


def get_connection(read_only=False):
    return DynamipsDriver(read_only)


def is_port_free(port):
    # netcat will exit with 0 only if the port is in use,
    # so a nonzero return value implies it is unused
    cmd = 'netcat', '0.0.0.0', port, '-w', '1'
    try:
        stdout, stderr = execute(*cmd, process_input='')
        return False
    except exception.ProcessExecutionError:
        return True


class PortPool(object):

    def __init__(self, start_port, end_port):
        self._ports = {}
        self._leases = {}
        self._start_port = start_port
        self._end_port = end_port

    def acquire(self, lease):
        port = self._leases.get(lease)
        if port:
            return port
        for i in xrange(0, 100):  # don't loop forever
            port = random.randint(self._start_port, self._end_port)
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
        if is_port_free(port):  # ajaxterm is not listening yet
            args = ["ajaxterm",
                    "-p", str(port),  # TODO: config host too
                    "-d",
                    "--command", "telnet -E localhost %s" % self.console]
            LOG.debug("Spawning process: %s" % args)
            self.__ajaxterm_process = execute(*args)
        return FLAGS.vncserver_proxyclient_address, port


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
        self._vif_driver = QuantumUdpChannelVIFDriver()

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

    def _class_for_flavor(self, flavorname):
        res = re.match(r'r1\.(.*)', flavorname)
        if res:
            model = res.group(1)
            try:
                # try direct model first
                return dynamips_lib.__dict__[model.upper()]
            except KeyError:
                raise exception.FlavorNotFound(
                    "Can not find router model %s" % model)
        else:
            raise exception.FlavorNotFound(
                "Dynamips accepts only r1.xxx flavors, got %s" % flavorname)

    def _class_for_instance(self, instance, inst_type):
        class_ = self._class_for_flavor(inst_type['name'])

        class CurrentRouter(RouterWrapper, class_):  # TODO: metaclass?
            pass
        return CurrentRouter

    def _instance_to_router(self, context, instance):
        inst_type = \
            instance_types.get_instance_type(instance["instance_type_id"])
        chassis = \
            db.instance_metadata_get(context, instance["id"]).get("chassis")
        C = self._class_for_instance(instance, inst_type)
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

    def _do_create_instance(self, context, instance, network_info):
        image = self._setup_image(context, instance)
        r = self._instance_to_router(context, instance)
        self._setup_network(context, r, instance, network_info)
        r.image = image
        r.mmap = False
        self._routers[instance["id"]] = r

    def spawn(self, context, instance, image_meta, injected_files,
              admin_password, network_info=[], block_device_info=None):
        LOG.debug("Spawning with network info %s" % network_info)
        self._do_create_instance(context, instance, network_info)
        self._router_by_name(instance["name"]).start()

    def destroy(self, instance, network_info, block_device_info=None):
        try:
            r = self._router_by_name(instance["name"])
        except exception.NotFound:
            r = None

        if r is not None:
            r.stop()  # TODO: error "unable to stop instance" may occur
            self._tear_down_network(r, instance, network_info)
            r.delete()
            del self._routers[r.name]
            # TODO: remove IOS image (?)
            # TODO: remove ramdisks (?)

    def reboot(self, instance, network_info, reboot_type,
               block_device_info=None):
        r = self._routers[instance["id"]]
        r.stop()
        r.start()

    def get_console_pool_info(self, console_type):
        # TODO: dunno
        raise NotImplementedError()

    def get_console_output(self, instance):
        # TODO: dunno
        raise NotImplementedError()

    @exception.wrap_exception()
    def get_vnc_console(self, instance):
        """Get host and port for TELNET console on instance

        Desperate its name, VNC console infrastructure is suitable for
        any protocols, including SSH and TELNET.
        """
        LOG.debug("Available instance ids are: %s" % self._routers.keys())
        r = self._routers[instance["id"]]
        port = self._port_pool.acquire(instance["id"])
        host, port = r.start_ajaxterm(port)
        return {'host': host, 'port': port, 'internal_access_path': None}

    def get_diagnostics(self, instance):
        # TODO: dunno
        raise NotImplementedError()

    def get_all_bw_usage(self, start_time, stop_time=None):
        """Return bandwidth usage info for each interface on each
           running VM"""
        # TODO: dunno
        raise NotImplementedError()

    def get_host_ip_addr(self):
        """
        Retrieves the IP address of the dom0
        """
        # no meaning in our implementation
        raise NotImplementedError()

    def snapshot(self, context, instance, image_id):
        """
        Snapshots the specified instance.

        :param context: security context
        :param instance: Instance object as returned by DB layer.
        :param image_id: Reference to a pre-created image that will
                         hold the snapshot.
        """
        # TODO: dunno
        raise NotImplementedError()

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
        if current_state == power_state.NOSTATE:
            self._do_create_instance(context, instance)
        current_state = self._current_state_for_instance(instance)

        if current_state == power_state.SHUTDOWN:
            self.power_on(instance)
            return self._current_state_for_instance(instance)
        else:
            return power_state.SHUTDOWN

    def rescue(self, context, instance, network_info, image_meta):
        """Rescue the specified instance"""
        raise NotImplementedError()

    def unrescue(self, instance, network_info):
        """Unrescue the specified instance"""
        raise NotImplementedError()

    def power_off(self, instance):
        """Power off the specified instance."""
        self._routers[instance["id"]].stop()  # TODO: semantics may differ

    def power_on(self, instance):
        """Power on the specified instance"""
        self._routers[instance["id"]].start()  # TODO: semantics may differ

    def get_available_resource(self):
        """Updates compute manager resource info on ComputeNode table.

        This method is called when nova-compute launches, and
        whenever admin executes "nova-manage service update_resource".

        :param ctxt: security context
        :param host: hostname that compute manager is currently running

        """
        dic = {'vcpus': 1,
               'memory_mb': 4096,
               'local_gb': 1028,
               'vcpus_used': 0,
               'memory_mb_used': 0,
               'local_gb_used': 0,
               'hypervisor_type': 'dynamips',
               'hypervisor_version': '0.2.7+',
               'cpu_info': '?'}
        return dic

    def refresh_security_group_rules(self, security_group_id):
        """This method is called after a change to security groups.

        All security groups and their associated rules live in the datastore,
        and calling this method should apply the updated rules to instances
        running the specified security group.

        An error should be raised if the operation cannot complete.

        """
        # TODO: stub, no meaning for us
        raise NotImplementedError()

    def refresh_security_group_members(self, security_group_id):
        """This method is called when a security group is added to an instance.

        This message is sent to the virtualization drivers on hosts that are
        running an instance that belongs to a security group that has a rule
        that references the security group identified by `security_group_id`.
        It is the responsibility of this method to make sure any rules
        that authorize traffic flow with members of the security group are
        updated and any new members can communicate, and any removed members
        cannot.

        Scenario:
            * we are running on host 'H0' and we have an instance 'i-0'.
            * instance 'i-0' is a member of security group 'speaks-b'
            * group 'speaks-b' has an ingress rule that authorizes group 'b'
            * another host 'H1' runs an instance 'i-1'
            * instance 'i-1' is a member of security group 'b'

            When 'i-1' launches or terminates we will receive the message
            to update members of group 'b', at which time we will make
            any changes needed to the rules for instance 'i-0' to allow
            or deny traffic coming from 'i-1', depending on if it is being
            added or removed from the group.

        In this scenario, 'i-1' could just as easily have been running on our
        host 'H0' and this method would still have been called.  The point was
        that this method isn't called on the host where instances of that
        group are running (as is the case with
        :py:meth:`refresh_security_group_rules`) but is called where references
        are made to authorizing those instances.

        An error should be raised if the operation cannot complete.

        """
        # TODO: stub, no meaning for us
        raise NotImplementedError()

    def refresh_provider_fw_rules(self):
        """This triggers a firewall update based on database changes.

        When this is called, rules have either been added or removed from the
        datastore.  You can retrieve rules with
        :py:meth:`nova.db.provider_fw_rule_get_all`.

        Provider rules take precedence over security group rules.  If an IP
        would be allowed by a security group ingress rule, but blocked by
        a provider rule, then packets from the IP are dropped.  This includes
        intra-project traffic in the case of the allow_project_net_traffic
        flag for the libvirt-derived classes.

        """
        # TODO: stub, no meaning for us
        raise NotImplementedError()

    def reset_network(self, instance):
        """reset networking for specified instance"""
        pass

    def set_admin_password(self, context, instance_id, new_pass=None):
        """
        Set the root password on the specified instance.

        The first parameter is an instance of nova.compute.service.Instance,
        and so the instance is being specified as instance.name. The second
        parameter is the value of the new password.
        """
        # TODO: may be useful, through console access maybe?
        raise NotImplementedError()

    def inject_file(self, instance, b64_path, b64_contents):
        """
        Writes a file on the specified instance.

        The first parameter is an instance of nova.compute.service.Instance,
        and so the instance is being specified as instance.name. The second
        parameter is the base64-encoded path to which the file is to be
        written on the instance; the third is the contents of the file, also
        base64-encoded.
        """
        # TODO: may be used for injecting config files
        raise NotImplementedError()

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

    def host_maintenance_mode(self, host, mode):
        """Start/Stop host maintenance window. On start, it triggers
        guest VMs evacuation."""
        # TODO: wtf
        raise NotImplementedError()

    def set_host_enabled(self, host, enabled):
        """Sets the specified host's ability to accept new instances."""
        # TODO: wtf
        raise NotImplementedError()

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

    def get_host_stats(self, refresh=False):
        """Return currently known host stats"""
        # TODO: implement
        # raise NotImplementedError()
        return {
            'host_name-description': 'Fake Host',
            'host_hostname': 'fake-mini',
            'host_memory_total': 8000000000,
            'host_memory_overhead': 10000000,
            'host_memory_free': 7900000000,
            'host_memory_free_computed': 7900000000,
            'host_other_config': {},
            'host_ip_address': '192.168.1.109',
            'host_cpu_info': {},
            'disk_available': 500000000000,
            'disk_total': 600000000000,
            'disk_used': 100000000000,
            'host_uuid': 'cedb9b39-9388-41df-8891-c5c9a0c0fe5f',
            'host_name_label': 'fake-mini'}

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

    def interface_stats(self, instance_name, iface_id):
        """
        Return performance counters associated with the given iface_id on the
        given instance_id.  These are returned as [rx_bytes, rx_packets,
        rx_errs, rx_drop, tx_bytes, tx_packets, tx_errs, tx_drop], where rx
        indicates receive, tx indicates transmit, bytes and packets indicate
        the total number of bytes or packets transferred, and errs and dropped
        is the total number of packets failed / dropped.

        All counters are long integers.

        This method is optional.  On some platforms (e.g. XenAPI) performance
        statistics can be retrieved directly in aggregate form, without Nova
        having to do the aggregation.  On those platforms, this method is
        unused.

        Note that this function takes an instance ID.
        """
        # TODO: may be useful, through direct connection and parsing maybe
        raise NotImplementedError()

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

    def add_to_aggregate(self, context, aggregate, host, **kwargs):
        """Add a compute host to an aggregate."""
        # TODO: wtf
        raise NotImplementedError()

    def remove_from_aggregate(self, context, aggregate, host, **kwargs):
        """Remove a compute host from an aggregate."""
        # TODO: wtf
        raise NotImplementedError()
