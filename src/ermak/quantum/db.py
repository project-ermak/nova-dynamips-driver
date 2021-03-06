import netaddr
from sqlalchemy import func

import quantum.db.api as db

from ermak.quantum import models
from ermak.quantum import configuration
from ermak.quantum import exceptions as plugin_exc
from sqlalchemy.orm.exc import NoResultFound


def initialize():
    options = {"sql_connection": configuration.DB_SQL_CONNECTION,
               "reconnect_interval": configuration.DB_RECONNECT_INTERVAL}
    db.configure_db(options)


def init_nets(session):
    port = configuration.UDP_PORT_START
    for net in netaddr.IPNetwork(configuration.UDP_POOL_CIDR).subnet(30):
        left, right = list(net.iter_hosts())
        if port > configuration.UDP_PORT_END:
            break
        link = models.UdpLink(str(net), str(left), str(right), port, port + 1)
        port += 2
        session.add(link)
    session.flush()


def are_nets_initialized(session):
    return session.query(func.count(models.UdpLink.cidr)).scalar() > 0


def allocate_udp_link(session, net_uuid):
    if not are_nets_initialized(session):
        init_nets(session)
    try:
        link = session.query(models.UdpLink).filter_by(net_uuid=None).first()
    except Exception:
        raise plugin_exc.PoolIsEmpty()
    link.net_uuid = net_uuid
    session.add(link)
    session.flush()
    return link


def deallocate_udp_link(session, net_uuid):
    link = session.query(models.UdpLink).filter_by(net_uuid=net_uuid).one()
    link.net_uuid = None
    session.add(link)
    session.flush()
    return link


def allocate_udp_for_port(session, net_uuid, port_uuid):
    link = session.query(models.UdpLink).filter_by(net_uuid=net_uuid).one()
    try:
        if link.left_port_uuid is None:
            link.left_port_uuid = port_uuid
            return link.left
        elif link.right_port_uuid is None:
            link.right_port_uuid = port_uuid
            return link.right
        else:
            raise plugin_exc.NoFreePorts()
    finally:
        session.add(link)
        session.flush()


def deallocate_udp_for_port(session, net_uuid, port_uuid):
    link = session.query(models.UdpLink)\
        .filter(
            models.UdpLink.net_uuid == net_uuid,
            (models.UdpLink.left_port_uuid == port_uuid) |
            (models.UdpLink.right_port_uuid == port_uuid)).one()
    try:
        if link.left_port_uuid == port_uuid:
            link.left_port_uuid = None
        elif link.right_port_uuid == port_uuid:
            link.right_port_uuid = None
        else:
            raise AssertionError("Not found allocation")
    finally:
        session.add(link)
        session.flush()


def get_udp_for_port(session, net_uuid, port_uuid):
    link = session.query(models.UdpLink)\
        .filter(
            models.UdpLink.net_uuid == net_uuid,
            (models.UdpLink.left_port_uuid == port_uuid) |
            (models.UdpLink.right_port_uuid == port_uuid)).one()
    if link.left_port_uuid == port_uuid:
        return models.UdpChannelPort(
            port_uuid, link.left, link.port_left, link.right, link.port_right)
    elif link.right_port_uuid == port_uuid:
        return models.UdpChannelPort(
            port_uuid, link.right, link.port_right, link.left, link.port_left)
    else:
        raise AssertionError("Unexpected state")


def get_attrs_for_port(session, port_uuid):
    try:
        info = session.query(models.PortAttribute) \
            .filter_by(port_uuid=port_uuid).one()
        return info.attributes
    except NoResultFound:
        return {}


def set_attrs_for_port(session, port_uuid, attributes):
    try:
        info = session.query(models.PortAttribute)\
            .filter_by(port_uuid=port_uuid).one()
        info.attributes = attributes
    except NoResultFound:
        info = models.PortAttribute(port_uuid, attributes)
    session.add(info)
    session.flush()
