class ErmakApiException(Exception):
    def __init__(self, msg):
        super(ErmakApiException, self).__init__(msg)

class HardwareNotSupported(ErmakApiException):
    def __init__(self, hardware):
        super(HardwareNotSupported, self).__init__(
            "Hardware %s not supported" % hardware)

class VmNotFound(Exception):
    def __init__(self, vm_id):
        super(VmNotFound, self).__init__(
            "VM or server with ID %s not found" % vm_id)
