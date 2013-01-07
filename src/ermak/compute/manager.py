# vim: tabstop=4 shiftwidth=4 softtabstop=4

import nova.context
from nova.compute import aggregate_states
from nova.compute.manager import publisher_id, wrap_instance_fault
from nova import exception
from nova import flags
import nova.image
from nova import log as logging
from nova.notifier import api as notifier
from nova import utils

from ermak import ajaxterm

FLAGS = flags.FLAGS
LOG = logging.getLogger("nova.compute.manager")

class ComputeManager(nova.compute.manager.ComputeManager):

    @exception.wrap_exception(notifier=notifier, publisher_id=publisher_id())
    @wrap_instance_fault
    def get_vnc_console(self, context, instance_uuid, console_type):
        """Return connection information for a vnc console."""
        context = context.elevated()
        LOG.debug(_("instance %s: getting vnc console"), instance_uuid)
        instance_ref = self.db.instance_get_by_uuid(context, instance_uuid)

        token = str(utils.gen_uuid())

        if console_type == 'novnc':
            # For essex, novncproxy_base_url must include the full path
            # including the html file (like http://myhost/vnc_auto.html)
            access_url = '%s?token=%s' % (FLAGS.novncproxy_base_url, token)
        elif console_type == 'xvpvnc':
            access_url = '%s?token=%s' % (FLAGS.xvpvncproxy_base_url, token)
        elif console_type == 'ajaxterm':
            access_url = '%s?token=%s' % (FLAGS.ajaxterm_base_url, token)
        else:
            raise exception.ConsoleTypeInvalid(console_type=console_type)

        # Retrieve connect info from driver, and then decorate with our
        # access info token
        connect_info = self.driver.get_vnc_console(instance_ref)
        connect_info['token'] = token
        connect_info['access_url'] = access_url

        return connect_info
