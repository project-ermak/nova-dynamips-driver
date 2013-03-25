from nova import db
from nova import flags
from nova import exception

FLAGS = flags.FLAGS

def get_ipam_lib(net_man):
    return NoOpIpamLib()


class NoOpIpamLib(object):
    """
    Because no real IP address management in Ermak project,
    this is no-op implementation.
    """

    def __init__(self, *args, **kwargs):
        pass

    def create_subnet(self, context, label, tenant_id,
                      quantum_net_id, priority, cidr=None,
                      gateway=None, gateway_v6=None, cidr_v6=None,
                      dns1=None, dns2=None):
        net = {"uuid": quantum_net_id,
               "project_id": tenant_id,
               "priority": priority,
               "label": label}
        admin_context = context.elevated()
        network = db.network_create_safe(admin_context, net)

    def delete_subnets_by_net_id(self, context, net_id, project_id):
        admin_context = context.elevated()
        tenant_id = project_id or FLAGS.quantum_default_tenant_id
        network = db.network_get_by_uuid(admin_context, net_id)
        db.network_delete_safe(context, network['id'])

    def get_networks_by_tenant(self, admin_context, tenant_id):
        return [] # loop over nets from IPAM backend

    def get_global_networks(self, admin_context):
        return self.get_networks_by_tenant(admin_context,
            FLAGS.quantum_default_tenant_id)

    def get_project_networks(self, admin_context):
        try:
            nets = db.network_get_all(admin_context.elevated())
        except exception.NoNetworksFound:
            return []
            # only return networks with a project_id set
        return [net for net in nets if net['project_id']]

    def get_project_and_global_net_ids(self, context, project_id):
        admin_context = context.elevated()

        # Decorate with priority
        priority_nets = []
        for tenant_id in (project_id, FLAGS.quantum_default_tenant_id):
            nets = self.get_networks_by_tenant(admin_context, tenant_id)
            for network in nets:
                priority = network['priority']
                priority_nets.append((priority, network['uuid'], tenant_id))

        # Sort by priority
        priority_nets.sort()

        # Undecorate
        return [(network_id, tenant_id)
            for priority, network_id, tenant_id in priority_nets]

    def allocate_fixed_ips(self, context, tenant_id, quantum_net_id,
                           network_tenant_id, vif_rec):
        return []

    def get_tenant_id_by_net_id(self, context, net_id, vif_id, project_id):
        # TODO: may be wrong
        return FLAGS.quantum_default_tenant_id

    def get_subnets_by_net_id(self, context, tenant_id, net_id, _vif_id=None):
        return []

    def get_routes_by_ip_block(self, context, block_id, project_id):
        """Returns the list of routes for the IP block"""
        return []

    def get_v4_ips_by_interface(self, context, net_id, vif_id, project_id):
        return []

    def get_v6_ips_by_interface(self, context, net_id, vif_id, project_id):
        return []

    def verify_subnet_exists(self, context, tenant_id, quantum_net_id):
        return True

    def deallocate_ips_by_vif(self, context, tenant_id, net_id, vif_ref):
        pass

    def get_allocated_ips(self, context, subnet_id, project_id):
        return []

    def get_floating_ips_by_fixed_address(self, context, fixed_address):
        return []
