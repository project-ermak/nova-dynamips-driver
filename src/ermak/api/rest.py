import json
from bson.errors import InvalidId
from bson.objectid import ObjectId
from flask import Flask, request
from mongokit.schema_document import ValidationError
import logging

from ermak.api import db
from ermak.api.openstack import OpenStackFacade
from ermak.api.views import *

app = Flask(__name__)
#app.facade = FakeFacade()
app.facade = OpenStackFacade(
    nova='http://localhost:8774/v2',
    quantum='http://localhost:9696')


def api_response(payload = None, status=200, headers=None):
    all_headers = {'Content-Type': 'application/json'}
    if headers is not None:
        all_headers.update(headers)
    if payload is None:
        payload = {}
    return json.dumps(payload), status, all_headers


class RequestContext(object):
    DEFAULT = 'default'

    def __init__(self, request=None):
        self.username = 'admin'
        self.api_key = 'qwerty'
        if request:
            self.tenant = request.view_args.get('tenant', self.DEFAULT)
        else:
            self.tenant = self.DEFAULT


@app.route("/<tenant>/instances", methods=["GET"])
def instance_list(tenant):
    instances = app.facade.get_instances(RequestContext(request))
    return api_response(status=200, payload=map(instance_to_json, instances))


@app.route("/<tenant>/instances/<id>", methods=["GET"])
def instance_get(tenant, id):
    try:
        instance_id = ObjectId(id)
    except InvalidId as e:
        return api_response(status=400, payload={'error': str(e)})
    try:
        instance = app.facade.get_instance(RequestContext(request), instance_id)
        return api_response(status=200, payload=instance_to_json(instance))
    except LookupError:
        return api_response(
            status=404, payload={'error': "Instance with id %s not found" % id})


@app.route("/<tenant>/instances", methods=["POST"])
def instance_create(tenant):
    try:
        content = json.loads(request.data)
    except Exception as e:
        return api_response(status=400, payload={'error': "Can not parse json: %s" % str(e)})
    try:
        instance = instance_from_json(content)
        instance['tenant'] = tenant
    except ValidationError as e:
        return api_response(status=400, payload={'error': str(e)})
    saved = app.facade.launch_instance(RequestContext(request), instance)
    return api_response(status=201, payload=instance_to_json(saved))



@app.route("/<tenant>/instances/<id>", methods=["DELETE"])
def instance_delete(tenant, id):
    try:
        instance_id = ObjectId(id)
    except InvalidId as e:
        return api_response(status=400, payload={'error': str(e)})
    try:
        instance = db.get_instance_by_id(tenant, instance_id)
    except LookupError:
        return api_response(
            status=404, payload={'error': "Instance with id %s not found" % id})
    destroyed = app.facade.destroy_instance(RequestContext(request), instance)
    return api_response(status=200, payload=instance_to_json(destroyed))


@app.route("/<tenant>/cards", methods=["GET"])
def network_adapters_list(tenant):
    cards = app.facade.get_network_cards(RequestContext(request))
    return api_response(status=200, payload=map(network_card_to_json, cards))


@app.route("/<tenant>/devices", methods=["GET"])
def device_types_list(tenant):
    types = app.facade.get_device_types(RequestContext(request))
    return api_response(status=200, payload=map(device_type_to_json, types))


@app.route("/<tenant>/instances/<id>/webconsole/<device>")
def get_webconsole(tenant, id, device):
    try:
        instance_id = ObjectId(id)
    except InvalidId as e:
        return api_response(status=400, payload={'error': str(e)})
    try:
        url = app.facade.get_webconsole(RequestContext(request), instance_id, device)
        return api_response(status=303, headers={'Location': url})
    except LookupError:
        return api_response(status=404)


if __name__ == '__main__':
    db.init_db("mongodb://localhost/ermak")
    logging.basicConfig(level=logging.DEBUG)
    app.run(debug=True)
