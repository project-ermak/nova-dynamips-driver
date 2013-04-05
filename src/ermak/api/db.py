from ermak.api import model
from pymongo import uri_parser
from mongokit import *

_conn = None
_db = None

def init_db(mongo_uri):
    global _conn
    global _db
    dbname = uri_parser.parse_uri(mongo_uri)['database']
    _conn = MongoClient(host=mongo_uri)
    _conn.register([model.Instance])
    _db = _conn[dbname]


def create_instance(instance):
    global _db
    instance.collection = _db.instances
    if instance.collection:
        instance.db = _db
        instance.connection = _conn
    return instance.save()


def get_instances_all(tenant):
    global _db
    return list(_db.instances.Instance.find({'tenant': tenant}))


def get_instance_by_id(tenant, instance_id):
    global _db
    query = {'tenant': tenant, '_id': instance_id}
    result = list(_db.instances.Instance.find(query))
    if len(result) == 0:
        raise LookupError("Can not find object with id %s" % instance_id)
    else:
        [instance] = result
        return instance

def update_instance(instance):
    return instance.save()


def delete_instance(instance_id):
    global _db
    return _db.instances.remove({'_id': instance_id})
