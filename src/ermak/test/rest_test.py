import json
import unittest
from bson.objectid import ObjectId

from pymongo.mongo_client import MongoClient

from ermak.api import rest, db


def db_instance(tenant):
    return {
        "tenant": tenant,
        "devices": [{
            "id": "C1",
            "status": "running",
            "instance_id": "nova-123",
            "name": "Computer",
            "hardware": "VM",
            "slots": [{
                "id": 0,
                "model": "Realtek",
                "editable": False}],
            "metadata": {
                "position": {
                    "x": 200,
                    "y": 200}}}],
        "wires": [{
            "left": {"device": "R1", "slot": 0, "port": 0},
            "right": {"device": "R2", "slot": 0, "port": 0},
            "id": "1",
            "quantum_id": "quantum-123"}]}


def view_instance(tenant = None, id = None):
    data = {
        "devices": [{
            "id": "C1",
            "name": "Computer",
            "hardware": "VM",
            "slots": [{
                "id": 0,
                "model": "Realtek",
                "editable": False}],
            "metadata": {
                "position": {
                    "x": 200,
                    "y": 200}}}],
        "wires": [{
            "left": {"device": "R1", "slot": 0, "port": 0},
            "right": {"device": "R2", "slot": 0, "port": 0},
            "id": "1"}]}
    if tenant is not None:
        data['tenant'] = tenant
    if id is not None:
        data['id'] = id
    return data


class RestTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        mongo = MongoClient("mongodb://localhost/")
        mongo.drop_database('ermak-test')
        cls.db = mongo['ermak-test']

    def setUp(self):
        self.app = rest.app.test_client()

        db.init_db("mongodb://localhost/ermak-test")

    def test_index_empty_instances(self):
        resp = self.app.get('/empty_tenant/instances')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, "[]")

    def test_index_instances(self):
        instance_id = self.db.instances.insert(db_instance('index_tenant'))
        resp = self.app.get('/index_tenant/instances')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            json.loads(resp.data),
            [view_instance('index_tenant', str(instance_id))])

    def test_get_instance_by_id(self):
        instance_id = \
            self.db.instances.insert(db_instance('get_tenant'), safe=True)
        resp = self.app.get('/get_tenant/instances/%s' % str(instance_id))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            json.loads(resp.data),
            view_instance('get_tenant', str(instance_id)))

    def test_get_instance_by_id_missing(self):
        instance_id = ObjectId()
        resp = self.app.get('/get_tenant/instances/%s' % str(instance_id))
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(
            json.loads(resp.data),
                {'error': "Instance with id %s not found" % str(instance_id)})

    def test_get_instance_by_wrong_id(self):
        resp = self.app.get('/get_tenant/instances/42')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            json.loads(resp.data),
            {'error': "42 is not a valid ObjectId"})

    def test_create_instance(self):
        resp = self.app.post(
            '/post_tenant/instances',
            data=json.dumps(view_instance()),
            headers=[('Content-Type', u'application/json')])
        self.assertEqual(resp.status_code, 201)
        payload = json.loads(resp.data)
        del payload['id']
        self.assertEqual(view_instance('post_tenant'), payload)

    def test_delete_instance_by_id(self):
        instance_id = \
            self.db.instances.insert(db_instance('del_tenant'), safe=True)
        resp = self.app.delete('/del_tenant/instances/%s' % str(instance_id))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            json.loads(resp.data),
            view_instance('del_tenant', str(instance_id)))
        self.assertEqual(list(self.db.instances.find({'_id': instance_id})), [])

if __name__ == '__main__':
    unittest.main()
