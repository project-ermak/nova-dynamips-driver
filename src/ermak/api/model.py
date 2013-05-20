from mongokit import Document, SchemaDocument


class Slot(SchemaDocument):
    structure = {
        'model': unicode,
        'parameters': dict,
        'editable': bool
    }
    required_fields = ['parameters', 'model', 'editable']


class Device(SchemaDocument):
    structure = {
        'id': basestring,
        'instance_id': basestring,
        'status': basestring,
        'software_id': basestring,
        'name': unicode,
        'hardware': unicode,
        'slots': [Slot],
        'metadata': dict}
    required_fields = ['id', 'name', 'hardware', 'slots', 'software_id']
    default_values = {'status': 'stopped'}


class Port(SchemaDocument):
    dot_notation_warning = True
    structure = {
        'device': unicode,
        'slot': int,
        'port': int,
        'quantum_id': basestring}
    required_fields = ['device', 'slot', 'port']


class Wire(SchemaDocument):
    structure = {
        'left': Port,
        'right': Port,
        'id': basestring,
        'quantum_id': basestring}
    required_fields = ['left', 'right']


class Instance(Document):
    structure = {
        'status': basestring,
        'tenant': unicode,
        'devices': [Device],
        'wires': [Wire]}
    required_fields = ['tenant']


class Software(SchemaDocument):
    structure = {
        'id': basestring,
        'name': basestring
    }
    required_fields = ['id', 'name']


class SlotProto(SchemaDocument):
    structure = {
        'model': basestring,       # default NC
        'editable': bool,
        'supported': [basestring]} # list of supported NCs


class DeviceType(Document):
    structure = {
        'id': basestring,
        'platform': basestring,
        'name': basestring,
        'metadata': dict,
        'parameters': dict,  # TODO: not used
        'software': [Software],
        'slots': [SlotProto]}
    required_fields = [
        'id', 'platform', 'name',
        'metadata', 'parameters', 'software', 'slots']


class PortGroup(SchemaDocument):
    structure = {
        'type': basestring,
        'count': int
    }
    required_fields = ['type', 'count']


class NetworkCard(Document):
    structure = {
        'model': basestring,
        'ports': [PortGroup]
    }
    required_fields = ['model', 'ports']
