from sqlalchemy import Column, Integer, String, Boolean

from quantum.db.models import BASE
from quantum.db.models import QuantumBase
from sqlalchemy.schema import UniqueConstraint, ForeignKey, PrimaryKeyConstraint


class UdpLink(BASE, QuantumBase):
    __tablename__ = 'udp_links'
    __table_args__ = (
        PrimaryKeyConstraint("cidr"),
    )

    net_uuid = Column(String(255), nullable=True)
    left_port_uuid = Column(String(255), nullable=True)
    right_port_uuid = Column(String(255), nullable=True)

    cidr = Column(String(255), nullable=False)
    left = Column(String(255), nullable=False)
    right = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)

    def __init__(self, cidr, left, right, port):
        self.cidr = cidr
        self.left = left
        self.right = right
        self.port = port

    def __repr__(self):
        return "<UdpLink(%s)>" % (self.cidr)


class UdpChannelPort(object):

    def __init__(self, port_uuid, src_address, src_port,
                 dst_address, dst_port):
        self.src_address = src_address
        self.src_port = src_port
        self.dst_address = dst_address
        self.dst_port = dst_port
        self.port_uuid = port_uuid

    def __iter__(self):
        data = {'src_address': self.src_address,
                'src_port': self.src_port,
                'dst_address': self.dst_address,
                'dst_port': self.dst_port,
                'port_uuid': self.port_uuid}
        return data.iteritems()
