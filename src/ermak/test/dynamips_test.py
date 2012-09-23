import os
import sys
from  nova.tests import test_virt_drivers
from nova import flags, test
import compute.dynamips

FLAGS = flags.FLAGS
FLAGS.state_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
FLAGS.image_service = 'nova.image.fake.FakeImageService'
FLAGS.instances_path = '/tmp/os_instances'
FLAGS.base_dir_name = 'base'

class DynamipsDriverTest(test_virt_drivers._VirtDriverTestCase):

    def setUp(self):
        self.driver_module = compute.dynamips
        compute.dynamips.dynamips_lib.NOSEND = True
        super(DynamipsDriverTest, self).setUp()

    def tearDown(self):
        self.connection.destroy(self._get_running_instance()[0], None)
        super(DynamipsDriverTest, self).tearDown()