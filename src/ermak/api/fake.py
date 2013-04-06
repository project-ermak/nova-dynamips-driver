from ermak.api import db

class FakeFacade(object):

    def launch_instance(self, ctx, instance):
        for device in instance['devices']:
            device['instance_id'] = 'nova-123'
            device['status'] = 'building'
        for wire in instance['wires']:
            wire['quantum_id'] = 'quantum-123'
        db.create_instance(instance)
        return instance


    def destroy_instance(self, ctx, instance):
        for device in instance['devices']:
            device['instance_id'] = 'nova-123'
            device['status'] = 'stopped'
        db.delete_instance(instance['_id'])
        return instance


    def update_instance_status(self, ctx, instance):
        for device in instance['devices']:
            device['status'] = 'running'
        return instance
