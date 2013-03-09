from quantum.common import exceptions

class PoolIsEmpty(exceptions.QuantumException):
    message = _("Unable to create new network. Number of networks" +
                "for the system has exceeded the limit")


class NoFreePorts(exceptions.QuantumException):
    message = _("Unable to create port. " +
                "Number of port on network exceed limit.")
