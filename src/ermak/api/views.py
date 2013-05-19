from bson.objectid import ObjectId
from ermak.api.model import *


def instance_to_json(instance):
    wires = map(wire_to_json, instance['wires'])
    devices = map(device_to_json, instance['devices'])
    return {
        'wires': wires,
        'devices': devices,
        'tenant': instance['tenant'],
        'id': str(instance['_id'])}


def wire_to_json(wire):
    def side_to_json(side):
        return {
            'device': side['device'],
            'slot': side['slot'],
            'port': side['port']}
    return {
        'left': side_to_json(wire['left']),
        'right': side_to_json(wire['right']),
        'id': wire['id']}


def device_to_json(device):
    slots = map(slot_to_json, device['slots'])
    return {
        'id': device['id'],
        'name': device['name'],
        'hardware': device['hardware'],
        'slots': slots,
        'metadata': device['metadata']}


def slot_to_json(slot):
    return {
        'id': slot['id'],
        'model': slot['model'],
        'editable': slot['editable']}



def instance_from_json(json_instance):
    instance = Instance()
    if json_instance.get('id') is not None:
        instance['_id'] = ObjectId(json_instance['id'])
    instance['wires'] = map(wire_from_json, json_instance['wires'])
    instance['devices'] = map(device_from_json, json_instance['devices'])
    return instance


def wire_from_json(json_wire):
    def side_to_json(side):
        p = Port()
        p['device'] = side['device']
        p['slot'] = side['slot']
        p['port'] = side['port']
        return p
    wire = Wire()
    wire['left'] = side_to_json(json_wire['left'])
    wire['right'] = side_to_json(json_wire['right'])
    wire['id'] = json_wire['id']
    return wire


def device_from_json(json_device):
    device = Device()
    device['id'] = json_device['id']
    device['name'] = json_device['name']
    device['hardware'] = json_device['hardware']
    device['slots'] = map(slot_from_json, json_device['slots'])
    device['metadata'] = json_device['metadata']
    return device


def slot_from_json(json_slot):
    slot = Slot()
    slot['id'] = json_slot['id']
    slot['model'] = json_slot['model']
    slot['editable'] = json_slot['editable']
    return slot


def device_type_to_json(device_type):
    return {
        'id': device_type['id'],
        'name': device_type['name'],
        'metadata': device_type['metadata'],
        'parameters': device_type['parameters'],
        'software': map(software_to_json, device_type['software']),
        'slots': map(slot_to_json, device_type['slots'])}


def software_to_json(software):
    return {'id': software['id'], 'name': software['name']}


def slot_to_json(slot):
    return {
        'model': slot['model'],
        'editable': slot['editable'],
        'supported': slot['supported']}


def network_card_to_json(nc):
    return {
        'model': nc['model'],
        'ports': map(portgroup_to_json, nc['ports'])}


def portgroup_to_json(portgroup):
    return {'type': portgroup['type'], 'count': portgroup['count']}
