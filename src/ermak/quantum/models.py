from quantum.db.model_base import BASEV2
from sqlalchemy import Column, Integer, String

import json

from sqlalchemy.schema import ForeignKey, PrimaryKeyConstraint


class UdpLink(BASEV2):
    __table_args__ = (
        PrimaryKeyConstraint("cidr"),
    )

    net_uuid = Column(String(36), nullable=True)
    left_port_uuid = Column(String(36), nullable=True)
    right_port_uuid = Column(String(36), nullable=True)

    cidr = Column(String(18), nullable=False)
    left = Column(String(15), nullable=False)
    right = Column(String(15), nullable=False)
    port_left = Column(Integer, nullable=False)
    port_right = Column(Integer, nullable=False)

    def __init__(self, cidr, left, right, lport, rport):
        self.cidr = cidr
        self.left = left
        self.right = right
        self.port_left = lport
        self.port_right = rport

    def __repr__(self):
        return "<UdpLink(%s)>" % self.cidr


class PortAttribute(BASEV2):
    __table_args__ = (PrimaryKeyConstraint("port_uuid"),)

    port_uuid = Column(
        String(36),
        ForeignKey('ports.id', ondelete='CASCADE'), nullable=True)
    attributes_json = Column(String(1024), nullable=False)

    def __init__(self, port_uuid, data):
        self.port_uuid = port_uuid
        self.attributes = data

    @property
    def attributes(self):
        return json.loads(self.attributes_json)

    @attributes.setter
    def attributes(self, data):
        self.attributes_json = json.dumps(data)

    def __repr__(self):
        return "<PortAttributes(%s,%s)>" % (
            self.port_uuid, self.attributes_json)


class UdpChannelPort(object):

    def __init__(self, port_id, src_address, src_port,
                 dst_address, dst_port):
        self.src_address = src_address
        self.src_port = src_port
        self.dst_address = dst_address
        self.dst_port = dst_port
        self.port_id = port_id

    def __iter__(self):
        data = {'src-address': self.src_address,
                'src-port': self.src_port,
                'dst-address': self.dst_address,
                'dst-port': self.dst_port,
                'port-id': self.port_id,
                'prefix-len': 30}
        return data.iteritems()
