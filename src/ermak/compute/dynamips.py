import os
from nova import flags, utils, exception, db
from nova import log as logging
from nova.openstack.common import cfg
from nova.virt import images
from nova.virt.libvirt import utils as libvirt_utils
from nova.virt.driver import ComputeDriver, InstanceInfo
from nova.compute import instance_types
from nova.compute import power_state

from dynagen import dynamips_lib

LOG = logging.getLogger(__name__)

dynamips_opts = [
    cfg.StrOpt('dynamips_host',
        default='localhost',
        help='Connection host for dynamips'),
    cfg.StrOpt('dynamips_port',
        default=7200,
        help='Connection port for dynamips')
    ]
FLAGS = flags.FLAGS
FLAGS.register_opts(dynamips_opts)


def get_connection(read_only=False):
    return DynamipsDriver()  # TODO: readonly support


class DynamipsClient(dynamips_lib.Dynamips):

    def __init__(self, host, port=7200, timeout=500):
        dynamips_lib.debug = LOG.debug
        old_nosend = dynamips_lib.NOSEND
        dynamips_lib.NOSEND = True
        super(DynamipsClient, self).__init__(host, port, timeout)
        dynamips_lib.NOSEND = old_nosend
        self.s.setblocking(1)
        self.s.connect((host, port))

    def vm_list(self):
        map(lambda x: x.split()[1], self.list("vm"))


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



class DynamipsDriver(ComputeDriver):
    """Driver for Dynamips CISCO emulator."""

    def __init__(self):
        self._routers = {}
        self.dynamips = DynamipsClient(FLAGS.dynamips_host, FLAGS.dynamips_port)

    def init_host(self, host):
        pass

    def get_info(self, instance):
        n = self._router_by_name(instance["name"])
        return {
            'state': n.os_state,
            'max_mem': int(instance_types
                         .get_instance_type(n.os_prototype.instance_type_id)
                         .get("memory_mb")) * 1024,
            'mem': n.ram * 1024,
            'num_cpu': 1,
            'cpu_time': 0 # cpuinfo?
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

    def _class_for_instance(self, instance):
        class CurrentRouter(RouterWrapper, dynamips_lib.Router): # TODO: mangle class
            pass
        return CurrentRouter

    def _instance_to_router(self, instance):
        inst_type = \
            instance_types.get_instance_type(instance["instance_type_id"])
        C = self._class_for_instance(instance)
        r = C(self.dynamips, name=instance["id"])
        r.os_name = instance["name"]
        r.ram = inst_type["memory_mb"]
        r.os_prototype = instance
        return r

    def _setup_image(self, context, instance):
        base_dir = os.path.join(FLAGS.instances_path, FLAGS.base_dir_name)
        if not os.path.exists(base_dir):
            libvirt_utils.ensure_tree(base_dir)
        path = os.path.abspath(os.path.join(base_dir, instance["image_ref"]))
        if not os.path.exists(path):
            images.fetch_to_raw(context, instance["image_ref"], path,
                instance["user_id"], instance["project_id"])
        return path

    def list_instances_detail(self):
        return map(lambda i: InstanceInfo(i.os_name, i.os_state),
            self._routers.itervalues())

    def spawn(self, context, instance, image_meta,
              network_info=None, block_device_info=None):
        image = self._setup_image(context, instance)
        r = self._instance_to_router(instance)
        r.image = image
        r.mmap = False
        r.start()
        self._routers[instance["id"]] = r

    def destroy(self, instance, network_info, block_device_info=None):
        try:
            r = self._router_by_name(instance["name"])
        except exception.NotFound:
            r = None

        if r is not None:
            r.stop() # TODO: error "unable to stop instance" may occurs
            r.delete()
            del self._routers[r.name]
            # remove IOS image (?)
            # remove ramdisks (?)


    def reboot(self, instance, network_info, reboot_type):
        r = self._routers[instance["id"]]
        r.stop()
        r.start()

    def snapshot_instance(self, context, instance_id, image_id):
        """
        Save current state of flash (?) and config
        """
        # TODO: dunno
        raise NotImplementedError()

    def get_console_pool_info(self, console_type):
        # TODO: dunno
        raise NotImplementedError()

    def get_console_output(self, instance):
        # TODO: dunno
        raise NotImplementedError()

    def get_vnc_console(self, instance):
        # TODO: dunno
        raise NotImplementedError()

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

    def resume_state_on_host_boot(self, context, instance, network_info):
        """resume guest state when a host is booted"""
        # TODO: ???
        raise NotImplementedError()

    def rescue(self, context, instance, network_info, image_meta):
        """Rescue the specified instance"""
        # TODO: wtf
        raise NotImplementedError()

    def unrescue(self, instance, network_info):
        """Unrescue the specified instance"""
        # TODO: wtf
        raise NotImplementedError()

    def power_off(self, instance):
        """Power off the specified instance."""
        self._routers[instance["id"]].stop() # TODO: semantics may differ

    def power_on(self, instance):
        """Power on the specified instance"""
        self._routers[instance["id"]].start() # TODO: semantics may differ

    def update_available_resource(self, ctxt, host):
        """Updates compute manager resource info on ComputeNode table.

        This method is called when nova-compute launches, and
        whenever admin executes "nova-manage service update_resource".

        :param ctxt: security context
        :param host: hostname that compute manager is currently running

        """
        try:
            service_ref = db.service_get_all_compute_by_host(ctxt, host)[0]
        except exception.NotFound:
            raise exception.ComputeServiceUnavailable(host=host)

        # Updating host information
        # TODO implement
        dic = {'vcpus': 1,
               'memory_mb': 4096,
               'local_gb': 1028,
               'vcpus_used': 0,
               'memory_mb_used': 0,
               'local_gb_used': 0,
               'hypervisor_type': 'dynamips',
               'hypervisor_version': '0.2.7+',
               'service_id': service_ref['id'],
               'cpu_info': '?'}

        compute_node_ref = service_ref['compute_node']
        if not compute_node_ref:
            LOG.info(_('Compute_service record created for %s ') % host)
            db.compute_node_create(ctxt, dic)
        else:
            LOG.info(_('Compute_service record updated for %s ') % host)
            db.compute_node_update(ctxt, compute_node_ref[0]['id'], dic)

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
        # TODO: wtf
        pass

    def ensure_filtering_rules_for_instance(self, instance_ref, network_info):
        """Setting up filtering rules and waiting for its completion.

        To migrate an instance, filtering rules to hypervisors
        and firewalls are inevitable on destination host.
        ( Waiting only for filtering rules to hypervisor,
        since filtering rules to firewall rules can be set faster).

        Concretely, the below method must be called.
        - setup_basic_filtering (for nova-basic, etc.)
        - prepare_instance_filter(for nova-instance-instance-xxx, etc.)

        to_xml may have to be called since it defines PROJNET, PROJMASK.
        but libvirt migrates those value through migrateToURI(),
        so , no need to be called.

        Don't use thread for this method since migration should
        not be started when setting-up filtering rules operations
        are not completed.

        :params instance_ref: nova.db.sqlalchemy.models.Instance object

        """
        # TODO: stub, no meaning for us
        raise NotImplementedError()

    def unfilter_instance(self, instance, network_info):
        """Stop filtering instance"""
        # TODO: wtf
        raise NotImplementedError()

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
        # TODO: stub, no meaning for us (?)
        raise NotImplementedError()

    def agent_update(self, instance, url, md5hash):
        """
        Update agent on the specified instance.

        The first parameter is an instance of nova.compute.service.Instance,
        and so the instance is being specified as instance.name. The second
        parameter is the URL of the agent to be fetched and updated on the
        instance; the third is the md5 hash of the file for verification
        purposes.
        """
        # TODO: wtf
        raise NotImplementedError()

    def inject_network_info(self, instance, nw_info):
        """inject network info for specified instance"""
        # TODO: stub, no meaning for us
        pass

    def poll_rebooting_instances(self, timeout):
        """Poll for rebooting instances"""
        # TODO: make list?
        raise NotImplementedError()

    def poll_rescued_instances(self, timeout):
        """Poll for rescued instances"""
        # TODO: wtf is rescue?
        raise NotImplementedError()

    def poll_unconfirmed_resizes(self, resize_confirm_window):
        """Poll for unconfirmed resizes."""
        # TODO: wtf
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
        # TODO: configure and start NIO brige
        # raise NotImplementedError()
        pass

    def unplug_vifs(self, instance, network_info):
        """Unplug VIFs from networks."""
        # TODO: unconfigure NIO bridge
        #raise NotImplementedError()
        pass

    def update_host_status(self):
        """Refresh host stats"""
        # TODO: wtf
        raise NotImplementedError()

    def get_host_stats(self, refresh=False):
        """Return currently known host stats"""
        # TODO: wtf
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

    def list_disks(self, instance_name):
        """
        Return the IDs of all the virtual disks attached to the specified
        instance, as a list.  These IDs are opaque to the caller (they are
        only useful for giving back to this layer as a parameter to
        disk_stats).  These IDs only need to be unique for a given instance.

        Note that this function takes an instance ID.
        """
        # TODO: no meaning for us
        raise NotImplementedError()

    def list_interfaces(self, instance_name):
        """
        Return the IDs of all the virtual network interfaces attached to the
        specified instance, as a list.  These IDs are opaque to the caller
        (they are only useful for giving back to this layer as a parameter to
        interface_stats).  These IDs only need to be unique for a given
        instance.

        Note that this function takes an instance ID.
        """
        # TODO: cXXXX show_hardware
        raise NotImplementedError()

    def resize(self, instance, flavor):
        """
        Resizes/Migrates the specified instance.

        The flavor parameter determines whether or not the instance RAM and
        disk space are modified, and if so, to what size.
        """
        # TODO: vm set_ram
        raise NotImplementedError()

    def block_stats(self, instance_name, disk_id):
        """
        Return performance counters associated with the given disk_id on the
        given instance_name.  These are returned as [rd_req, rd_bytes, wr_req,
        wr_bytes, errs], where rd indicates read, wr indicates write, req is
        the total number of I/O requests made, bytes is the total number of
        bytes transferred, and errs is the number of requests held up due to a
        full pipeline.

        All counters are long integers.

        This method is optional.  On some platforms (e.g. XenAPI) performance
        statistics can be retrieved directly in aggregate form, without Nova
        having to do the aggregation.  On those platforms, this method is
        unused.

        Note that this function takes an instance ID.
        """
        # TODO: no meaning for us
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

    def legacy_nwinfo(self):
        """
        Indicate if the driver requires the legacy network_info format.
        """
        # TODO: wtf
        return True

    def manage_image_cache(self, context):
        """
        Manage the driver's local image cache.

        Some drivers chose to cache images for instances on disk. This method
        is an opportunity to do management of that cache which isn't directly
        related to other calls into the driver. The prime example is to clean
        the cache and remove images which are no longer of interest.
        """
        # TODO: wtf

    def add_to_aggregate(self, context, aggregate, host, **kwargs):
        """Add a compute host to an aggregate."""
        # TODO: wtf
        raise NotImplementedError()

    def remove_from_aggregate(self, context, aggregate, host, **kwargs):
        """Remove a compute host from an aggregate."""
        # TODO: wtf
        raise NotImplementedError()

    def get_volume_connector(self, instance):
        """Get connector information for the instance for attaching to volumes.

        Connector information is a dictionary representing the ip of the
        machine that will be making the connection and and the name of the
        iscsi initiator as follows::

            {
                'ip': ip,
                'initiator': initiator,
            }
        """
        # TODO: no meaning for us (nvram?)
        raise NotImplementedError()

