from ermak.api import db

def launch_instance(ctx, instance):
    for device in instance['devices']:
        device['instance_id'] = 'nova-123'
        device['status'] = 'running'
    for wire in instance['wires']:
        wire['quantum_id'] = 'quantum-123'
    db.create_instance(instance)
    return instance


def destroy_instance(ctx, instance):
    for device in instance['devices']:
        device['instance_id'] = 'nova-123'
        device['status'] = 'stopped'
    db.delete_instance(instance['_id'])
    return instance
