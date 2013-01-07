#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4 softtabstop=4

"""Module for Ajax proxying."""

from nova import flags
from nova.openstack.common import cfg

vnc_opts = [
    cfg.StrOpt('ajaxterm_base_url',
        default='http://127.0.0.1:8022/',
        help='location of AjaxTerm console proxy, in the form '
             '"http://127.0.0.1:8022/"'),
    cfg.StrOpt('ajaxterm_portrange',
        default='10000-12000',
        help='Range of ports that ajaxterm should try to bind')
]

FLAGS = flags.FLAGS
FLAGS.register_opts(vnc_opts)
