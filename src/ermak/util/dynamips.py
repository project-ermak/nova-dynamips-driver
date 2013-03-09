from dynagen import dynamips_lib
from dynagen.dynamips_lib import send

class DynamipsClient(dynamips_lib.Dynamips):

    def __init__(self, host, port=7200, timeout=500):
        old_nosend = dynamips_lib.NOSEND
        dynamips_lib.NOSEND = True
        super(DynamipsClient, self).__init__(host, port, timeout)
        dynamips_lib.NOSEND = old_nosend
        if not dynamips_lib.NOSEND:
            self.s.setblocking(1)
            try:
                self.s.connect((host, port))
            except:
                raise dynamips_lib.DynamipsError('Could not connect to server')

    def vm_list(self):
        map(lambda x: x.split()[1], self.list("vm"))


class Bridge(dynamips_lib.Bridge):

    def delete(self):
        send(self._d, 'nio_bridge delete ' + self._name)
