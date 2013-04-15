#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2013 Nikolay Sokolov
# Copyright (c) 2012 OpenStack LLC
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

"""Eventlet WSGI Service to proxy VNC for XCP protocol."""

from urllib2 import URLError
from urlparse import urlparse, parse_qs, urlunparse
import webob

from eventlet.green import urllib2

from nova import context
from nova import flags
from nova.consoleauth import rpcapi
from nova.openstack.common import log as logging
from nova.openstack.common import cfg
from nova.openstack.common import rpc
from nova import version
from nova import wsgi


LOG = logging.getLogger("nova.ajaxterm.ajaxterm_proxy")

ajaxterm_proxy_opts = [
    cfg.IntOpt('ajaxterm_proxy_port',
        default=8022,
        help='Port that the AjaxTem console proxy should bind to'),
    cfg.StrOpt('ajaxterm_proxy_host',
        default='0.0.0.0',
        help='Address that the AjaxTerm console proxy should bind to'),
    ]

FLAGS = flags.FLAGS
FLAGS.register_opts(ajaxterm_proxy_opts)

flags.DECLARE('consoleauth_topic', 'nova.consoleauth')

def token_from_url(url):
    return parse_qs(urlparse(url).query).get('token')[0]

class AjaxTermConsoleProxy(object):
    """Class to use the ajaxterm protocol to proxy ajaxterm consoles."""

    def __init__(self):
        self._consoleauth = rpcapi.ConsoleAuthAPI()
        self._tokens = {}

    def __call__(self, environ, start_response):
        try:
            req = webob.Request(environ)
            LOG.audit(_("Request: %s"), req)
            token = req.params.get('token') or \
                    req.headers.get("Referer") and token_from_url(req.headers.get("Referer"))
            if not token:
                LOG.audit(_("Request made with missing token: %s"), req)
                start_response('400 Invalid Request',
                    [('content-type', 'text/html')])
                return "Invalid Request"

            ctxt = context.get_admin_context()
            connect_info = self._tokens.get(token)
            if not connect_info:
                connect_info =  self._consoleauth.check_token(ctxt, token)

            if not connect_info:
                LOG.audit(_("Request made with invalid token: %s"), req)
                start_response('401 Not Authorized',
                    [('content-type', 'text/html')])
                return "Not Authorized"

            # TODO: ajaxterm GET is broken with encoded sybmols
            #query = parse_qs(req.query_string)
            #query['token'] = token
            #query_string = urlencode(query)

            query_string = req.query_string + "&token=" + token
            remote_url = urlunparse(
                ["http", "%(host)s:%(port)s" % connect_info,
                 req.path, "",
                 query_string, ""])

            LOG.audit("Proxying request with remote url %s" % remote_url)
            try:
                data = urllib2.urlopen(remote_url, req.body)
                start_response(str(data.getcode()), data.info().items())
                return data.read()
            except URLError:
                start_response('500 Server error')
                return "Can not open connection to compute host"
        except Exception as e:
            LOG.audit(_("Unexpected error: %s"), e)


def get_wsgi_server():
    LOG.audit(_("Starting nova-ajaxterm-proxy node (version %s)"),
        version.version_string_with_vcs())

    return  wsgi.Server("AjaxTerm console proxy",
        AjaxTermConsoleProxy(),
        host=FLAGS.ajaxterm_proxy_host,
        port=FLAGS.ajaxterm_proxy_port)
