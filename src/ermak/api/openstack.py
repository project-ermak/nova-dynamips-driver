import logging

from bson.objectid import ObjectId
from novaclient.client import Client as NovaClient
from ermak.api import db
from ermak.api.errors import HardwareNotSupported, VmNotFound
from ermak.api.model import DeviceType, Slot, Software, PortGroup, NetworkCard, SlotProto
from ermak.udpclient import QuantumUdpClient

DELETED_STATE = 'deleted'
TYPENAMES = {
    'f': 'FastEthernet',
    'g': 'GigabitEthernet',
    'a': 'ATM',
    's': 'Serial',
    'e': 'Ethernet',
    'p': 'POS', # POS-OC3
    'i': 'IDS', # IDS
    'an': 'NAM' # NAM
}
ETHERNET_LETTERS = ['e', 'f', 'g']
QEMU_CARDS = ['e1000']  # cards for qemu are not supported
DEFAULT_QEMU_CARD = QEMU_CARDS[0]

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

        devices_dict = dict(map(lambda d: (d['id'], d), instance['devices']))
        def port_attrs(wire_side):
            device = devices_dict[wire_side['device']]
            slot = wire_side['slot']
            slot_model = device['slots'][slot]['model']
            return {
                'slot-id': slot,
                'port-id': wire_side['port'],
                'slot-model': slot_model}

        for wire in instance['wires']:
            print wire
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
        print conn_info
        for device in instance['devices']:
            print "Launching %s" % device
            conn = conn_info.get(device['id'])
            logging.debug("Connection info for instance: %s" % conn)
            server = nova.servers.create(
                name="%s-%s-%s" % (instance['_id'], device['id'], device['name']),
                image=device['software_id'],
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
        result = []

        result.extend(self._dynamips_network_cards())
        result.extend(self._qemu_network_cards())

        return result

    def _dynamips_network_cards(self):
        from dynagen import dynamips_lib
        dynamips_lib.NOSEND = True

        def if_letter_to_type(letter):
            return TYPENAMES[letter]

        cards = {}
        fake_dynamips = dynamips_lib.Dynamips('example.com')
        for (platform, chassis_dict) in dynamips_lib.ADAPTER_MATRIX.iteritems():
            router_class = getattr(dynamips_lib, platform.capitalize(), None)
            if not router_class:
                continue
            for (chassis, adapters_dict) in chassis_dict.iteritems():
                for (slot, adapters) in adapters_dict.iteritems():
                    if isinstance(adapters, basestring):
                        adapter_list = [adapters]
                    else:
                        adapter_list = adapters
                    for adapter in adapter_list:
                        if adapter in cards:
                            continue
                        classname = adapter.replace('-', '_')
                        fake_router = router_class(fake_dynamips, chassis=chassis)
                        class_ = getattr(dynamips_lib, classname, None)
                        if class_:
                            if fake_router.slot[slot] and \
                               adapter == fake_router.slot[slot].adapter:
                                instance = fake_router.slot[slot]
                            else:
                                instance = class_(fake_router, slot)
                            ports = []
                            for (if_letter, if_dict) in instance.interfaces.iteritems():
                                if_type = if_letter_to_type(if_letter)
                                count = len(if_dict)
                                port_group = PortGroup({
                                    'type': if_type,
                                    'count': count})
                                ports.append(port_group)
                            card = NetworkCard({
                                'model': adapter,
                                'ports': ports})
                            cards[adapter] = card

        return list(cards.itervalues())

    def _qemu_network_cards(self):
        result = []

        card = NetworkCard({
            'model': QEMU_CARDS[0],
            'ports': [PortGroup({
                'type': TYPENAMES['g'], 'count': 1})]})
        result.append(card)

        return result

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

        for t in self._qemu_types(flavors):
            software = self._platform_images(nova, None)
            t['software'] = software
            result.append(t)

        return result

    def get_webconsole(self, ctx, id, device_id):
        instance = db.get_instance_by_id(ctx.tenant, id)
        device = dict(
            map(lambda d: (d['id'], d), instance['devices']))[device_id]

        nova = self._get_nova_client(ctx)
        server = nova.servers.get(device['instance_id'])
        console = nova.servers.get_vnc_console(server, 'ajaxterm')
        return console['console']['url']

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

    def _qemu_types(self, flavors):
        result = []
        for flavor in flavors:
            if flavor.startswith('c1'):
                continue
            type = DeviceType({
                'id': flavor.name,
                'platform': 'qemu',
                'name': "Virtual Machine %s CPU %s MB" % (
                    flavor.vcpus, flavor.ram),
                'metadata': {},
                'parameters': {},
                'software': [],
                'slots': [SlotProto({
                    'model': DEFAULT_QEMU_CARD,
                    'editable': False,
                    'supported': [DEFAULT_QEMU_CARD]})]})
            result.append(type)

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
                    slot = SlotProto({
                        'model': dynamips_slot,
                        'editable': False,
                        'supported': [dynamips_slot]})
                else:
                    slot = SlotProto({
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
            if flavor.name == device['hardware']:
                return flavor.id
        raise HardwareNotSupported(device['hardware'])

