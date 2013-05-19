import logging

from bson.objectid import ObjectId
from novaclient.client import Client as NovaClient
from ermak.api import db
from ermak.api.errors import HardwareNotSupported, VmNotFound
from ermak.api.model import DeviceType, Slot, Software
from ermak.udpclient import QuantumUdpClient

DELETED_STATE = 'deleted'

class OpenStackFacade(object):

    def __init__(self,
                 keystone=None, nova=None, quantum=None):
        if keystone is not None:
            if nova is not None:
                raise Exception("nova and keystone are mutually exclusive")
            if quantum is not None:
                raise Exception("nova and keystone are mutually exclusive")
            raise NotImplementedError("keystone auth is not implemented")
        else:
            def _get_nova_client(ctx):
                return NovaClient("2",
                    ctx.username,
                    ctx.api_key,
                    ctx.tenant,
                    auth_url=nova,
                    auth_system=None) # TODO
            def _get_quantum_client(ctx):
                return QuantumUdpClient(
                    username=ctx.username,
                    token=ctx.api_key,
                    tenant_name=ctx.tenant,
                    endpoint_url=quantum,
                    auth_strategy='none') # TODO
            self._get_nova_client = _get_nova_client
            self._get_quantum_client = _get_quantum_client


    def launch_instance(self, ctx, instance):
        # TODO: validate
        nova = self._get_nova_client(ctx)
        quantum = self._get_quantum_client(ctx)
        instance['_id'] = ObjectId()
        conn_info = {} # [device_id] = [(net,port)]

        def add_conn_info(device, net, port):
            conn = conn_info.get(device)
            if conn is None:
                conn = []
                conn_info[device] = conn
            conn.append({"net-id": net, "v4-fixed-ip": "", "port-id": port})

        def create_port(instance_id, net_id, wire_id, side):
            return quantum.create_port({
                'port': {
                    'tenant_id': ctx.tenant,
                    'network_id': net_id,
                    'name': "%s-%s-%s" % (
                        instance_id, wire_id, side)}})['port']

        def port_attrs(wire_side):
            return {
                'slot-id': wire_side['slot'],
                'port-id': wire_side['port']}

        for wire in instance['wires']:
            net = quantum.create_network({
                'network': {
                    'name': "%s-%s" % (instance['_id'], wire['id']),
                    'tenant_id': ctx.tenant}})['network']
            left = create_port(instance['_id'], net['id'], wire['id'], 'left')
            wire['left']['quantum_id'] = left['id']
            right = create_port(instance['_id'], net['id'], wire['id'], 'right')
            wire['right']['quantum_id'] = right['id']
            left_attrs = port_attrs(wire['left'])
            right_attrs = port_attrs(wire['right'])
            quantum.set_port_attrs(ctx.tenant, net['id'], left['id'], left_attrs)
            quantum.set_port_attrs(ctx.tenant, net['id'], right['id'], right_attrs)
            add_conn_info(wire['left']['device'], net['id'], left['id'])
            add_conn_info(wire['right']['device'], net['id'], right['id'])
            wire['quantum_id'] = net['id']
        for device in instance['devices']:
            conn = conn_info.get(device['id'])
            logging.debug("Connection info for instance: %s" % conn)
            server = nova.servers.create(
                name="%s-%s-%s" % (instance['_id'], device['id'], device['name']),
                image=self._image_for_device(nova, device),
                flavor=self._flavor_for_device(nova, device),
                nics=conn,
                scheduler_hints=[]) # TODO: use instance type
            device['instance_id'] = server.id
            device['status'] = server.status.lower()
        db.create_instance(instance)
        return instance

    def destroy_instance(self, ctx, instance):
        nova = self._get_nova_client(ctx)
        quantum = self._get_quantum_client(ctx)

        for device in instance['devices']:
            try:
                nova.servers.delete(device['instance_id'])
            except Exception as e:
                logging.error("Can not delete server", e)
            device['status'] = DELETED_STATE

        for wire in instance['wires']:
            try:
                quantum.delete_port(wire['left']['quantum_id'])
            except Exception as e:
                logging.error("Can not delete left wire side", e)
            try:
                quantum.delete_port(wire['right']['quantum_id'])
            except Exception as e:
                logging.error("Can not delete right wire side", e)
            try:
                quantum.delete_network(wire['quantum_id'])
            except Exception as e:
                logging.error("Can not delete wire side", e)

        db.delete_instance(instance['_id'])
        return instance


    def update_instance_status(self, ctx, instance):
        nova = self._get_nova_client(ctx)

        all_servers = nova.servers.list()
        servers = dict(map(lambda s: (s.id, s), all_servers))
        for device in instance['devices']:
            server = servers.get(device['instance_id'])
            if server:
                device['status'] = server.status.lower()
            elif device['status'] != DELETED_STATE:
                raise VmNotFound(device['id'])
        return db.update_instance(instance)

    def get_instance(self, ctx, id):
        return db.get_instance_by_id(ctx.tenant, id)

    def get_instances(self, ctx):
        return db.get_instances_all(ctx.tenant)

    def get_network_cards(self, ctx):
        return [] # TODO

    def get_device_types(self, ctx):
        result = []

        nova = self._get_nova_client(ctx)
        flavors = nova.flavors.list()
        flavor_names = map(lambda f: f.name, flavors)

        for t in self._dynamips_types():
            print t['id'], flavor_names
            if not flavor_names.count(t['id']):
                continue
            software = self._platform_images(nova, t['platform'])
            if software:
                t['software'] = software
                result.append(t)

        return result

    def get_webconsole(self, ctx, id, device_id):
        pass

    def _dynamips_flavor(self, model):
        return 'c1.' + model

    def _platform_images(self, nova, platform):
        images = nova.images.list()
        result = []
        for image in images:
            platform_meta = image.metadata.get('dynamips_platform')
            print platform_meta, platform
            if platform_meta == platform:
                software = Software({
                    'id': image.id,
                    'name': image.name})
                result.append(software)
        return result

    def _dynamips_types(self):
        from dynagen import dynamips_lib

        def make_slots_list(slots_dict):
            slots = []
            for i in xrange(100):
                dynamips_slot = slots_dict.get(i)
                if not dynamips_slot:
                    return slots
                if isinstance(dynamips_slot, basestring):
                    slot = Slot({
                        'model': dynamips_slot,
                        'editable': False,
                        'supported': [dynamips_slot]})
                else:
                    slot = Slot({
                        'model': None,
                        'editable': True,
                        'supported': list(dynamips_slot)})
                slots.append(slot)

        result = []
        print dynamips_lib.ADAPTER_MATRIX
        for (platform, chassis_dict) in dynamips_lib.ADAPTER_MATRIX.iteritems():
            cls = getattr(dynamips_lib, platform.capitalize(), None)
            if not cls:
                continue
            for (chassis, slots_dict) in chassis_dict.iteritems():
                if chassis == '':
                    chassis = platform[int(platform[0] == 'c'):]
                slots = make_slots_list(slots_dict)
                hwtype = DeviceType({
                    'id': self._dynamips_flavor(chassis),
                    'platform': platform,
                    'name': 'Cisco ' + chassis,
                    'metadata': {},
                    'parameters': {},
                    'software': [],  # this must be filled later
                    'slots': slots})
                result.append(hwtype)
        return result

    def _flavor_for_device(self, nova, device):
        flavors = nova.flavors.list()
        for flavor in flavors:
            segments = flavor.name.split('.', 1)
            if len(segments) == 2 and\
               segments[1].lower() == device['hardware'].lower():
                return flavor.id
        raise HardwareNotSupported(device['hardware'])

    def _image_for_device(self, nova, device):
        images = nova.images.list()
        for image in images:
            if device['hardware'].lower() in image.name.lower():
                return image.id
        raise HardwareNotSupported(device['hardware'])

