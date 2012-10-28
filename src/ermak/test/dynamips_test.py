import os
import sys
import nova
import nova.db
from nova.tests import test_virt_drivers
from nova import flags, test, context, exception
from nova.tests import utils as test_utils
import compute.dynamips

FLAGS = flags.FLAGS
FLAGS.state_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
FLAGS.image_service = 'nova.image.fake.FakeImageService'
FLAGS.instances_path = '/tmp/os_instances'
FLAGS.base_dir_name = 'base'

class DynamipsDriverTest(test_virt_drivers._VirtDriverTestCase):

    def _get_running_instance(self):
        instance_ref = test_utils.get_test_instance()
        instance_ref['instance_type_id'] = self.router_type_id
        network_info = test_utils.get_test_network_info()
        image_info = test_utils.get_test_image_info(None, instance_ref)
        self.connection.spawn(self.ctxt, instance=instance_ref,
            image_meta=image_info,
            network_info=network_info)
        return instance_ref, network_info

    def setUp(self):
        self.driver_module = compute.dynamips
        compute.dynamips.dynamips_lib.NOSEND = True
        super(DynamipsDriverTest, self).setUp()
        self.router_type_id = nova.db.instance_type_create(
            context.get_admin_context(),
                {'name': 'r1.c2691',
                 'memory_mb': 128,
                 'vcpus': 1,
                 'root_gb': 0,
                 'ephemeral_gb': 0,
                 'flavorid': 6}
        )["id"]

    def tearDown(self):
        self.connection.destroy(self._get_running_instance()[0], None)
        super(DynamipsDriverTest, self).tearDown()