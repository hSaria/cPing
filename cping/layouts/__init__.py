"""Generic code and base classes for layouts."""
import cping.protocols


class Layout:
    """A layout base class. Subclasses must implement `__call__`."""
    def __init__(self, protocol):
        """Constructor.

        Args:
            protocol (cping.protocols.Ping): The ping protocol.

        Raises:
            TypeError: If `protocol` is not an instance of `cping.protocols.Ping`.
        """
        if not isinstance(protocol, cping.protocols.Ping):
            raise TypeError('protocol must be an instance of '
                            'cping.protocols.Ping')

        self._hosts = []
        self._protocol = protocol

    def __call__(self):
        """Begins rendering the layout. If any finalizers need to run before
        exiting, wrap the code in a try-finally block."""
        raise NotImplementedError('cping.layouts.Layout is a base class; it '
                                  'does not implement __call__')

    @property
    def hosts(self):
        """The list of hosts (instances of cping.protocols.Host)."""
        return self._hosts.copy()

    @property
    def protocol(self):
        """The ping protocol."""
        return self._protocol

    def add_host(self, address):
        """Adds a host to `self.hosts`. Returns the newly-created host.

        Args:
            address (str): Ping destination.

        Raises:
            TypeError: If `address` is not a string.
        """
        if not isinstance(address, str):
            raise TypeError('address must be a string')

        host = self.protocol(address)
        self._hosts.append(host)

        return host

    def remove_host(self, host):
        """Removes a host from `self.hosts`.

        Args:
            host (cping.protocols.Host): The host to remove.

        Raises:
            ValueError: If `host` is not in `self.hosts`.
        """
        self._hosts.remove(host)
