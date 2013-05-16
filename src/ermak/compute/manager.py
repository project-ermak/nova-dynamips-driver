# vim: tabstop=4 shiftwidth=4 softtabstop=4

import nova.context
from nova.compute import aggregate_states
from nova.compute.manager import publisher_id, wrap_instance_fault
from nova import exception
from nova import flags
import nova.image
from nova.openstack.common import log as logging
from nova.openstack.common.notifier import api as notifier
from nova import utils

from ermak import ajaxterm

FLAGS = flags.FLAGS
LOG = logging.getLogger("nova.compute.manager")

class ComputeManager(nova.compute.manager.ComputeManager):

    @exception.wrap_exception(notifier=notifier, publisher_id=publisher_id())
    @wrap_instance_fault
    def validate_console_port(self, ctxt, instance, port, console_type):
        if console_type == 'ajaxterm':
            console_info = self.driver.get_web_console(instance)
        else:
            console_info = self.driver.get_vnc_console(instance)
        return console_info['port'] == port

    @exception.wrap_exception(notifier=notifier, publisher_id=publisher_id())
    @wrap_instance_fault
    def get_vnc_console(self, context, console_type, instance):
        """Return connection information for a vnc console."""
        context = context.elevated()
        LOG.debug(_("Getting vnc console"), instance=instance)
        token = str(utils.gen_uuid())

        if console_type == 'ajaxterm':
            access_url = '%s?token=%s' % (FLAGS.ajaxterm_base_url, token)
            connect_info = self.driver.get_web_console(instance)
            connect_info['token'] = token
            connect_info['access_url'] = access_url
            return connect_info
        elif console_type == 'novnc':
            # For essex, novncproxy_base_url must include the full path
            # including the html file (like http://myhost/vnc_auto.html)
            access_url = '%s?token=%s' % (FLAGS.novncproxy_base_url, token)
        elif console_type == 'xvpvnc':
            access_url = '%s?token=%s' % (FLAGS.xvpvncproxy_base_url, token)
        else:
            raise exception.ConsoleTypeInvalid(console_type=console_type)

        # Retrieve connect info from driver, and then decorate with our
        # access info token
        connect_info = self.driver.get_vnc_console(instance)
        connect_info['token'] = token
        connect_info['access_url'] = access_url

        return connect_info
