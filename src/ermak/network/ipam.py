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
        pass

    def delete_subnets_by_net_id(self, context, net_id, project_id):
        pass

    def get_global_networks(self, admin_context):
        return []

    def get_project_networks(self, admin_context):
        return []

    def get_project_and_global_net_ids(self, context, project_id):
        return []

    def allocate_fixed_ips(self, context, tenant_id, quantum_net_id,
                           network_tenant_id, vif_rec):
        return []

    def get_tenant_id_by_net_id(self, context, net_id, vif_id, project_id):
        return project_id

    def get_subnets_by_net_id(self, context, tenant_id, net_id, _vif_id=None):
        return [None, None]

    def get_routes_by_ip_block(self, context, block_id, project_id):
        """Returns the list of routes for the IP block"""
        return []

    def get_v4_ips_by_interface(self, context, net_id, vif_id, project_id):
        return []

    def get_v6_ips_by_interface(self, context, net_id, vif_id, project_id):
        return []

    def verify_subnet_exists(self, context, tenant_id, quantum_net_id):
        pass

    def deallocate_ips_by_vif(self, context, tenant_id, net_id, vif_ref):
        pass

    def get_allocated_ips(self, context, subnet_id, project_id):
        return []

    def get_floating_ips_by_fixed_address(self, context, fixed_address):
        return []
