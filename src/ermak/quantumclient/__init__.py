from quantumclient.v2_0.client import Client, APIParamsCall

class QuantumUdpClient(Client):

    channels_path = "/extensions/udp/tenants/%s/networks/%s/channels"
    channel_path =\
    "/extensions/udp/tenants/%s/networks/%s/channels/%s"

    attr_path = "/extensions/attributes/tenants/%s" +\
                "/networks/%s/networks/%s/ports/%s"

    def __init__(self, *args, **kwargs):
        super(QuantumUdpClient, self).__init__(*args, **kwargs)

    @APIParamsCall
    def list_channels(self, tenant, net_id, **params):
        return self.get(self.channels_path % (tenant, net_id),
            params=params)

    @APIParamsCall
    def show_channel(self, tenant, net_id, port_id, **params):
        return self.get(self.channel_path % (tenant, net_id, port_id),
            params=params)

    @APIParamsCall
    def show_port_attrs(self, tenant, net_id, port_id, **params):
        return self.get(self.attr_path% (tenant, net_id, port_id),
            params=params)

    @APIParamsCall
    def set_port_attrs(self, tenant, net_id, port_id, attributes):
        body = {
            'port': {
                'port-id': port_id,
                'attributes': attributes
            }
        }
        return self.put(self.attr_path % (tenant, net_id, port_id), body=body)
