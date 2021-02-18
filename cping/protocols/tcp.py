"""TCP ping."""
import socket
import time

import cping.protocols


class Ping(cping.protocols.Ping):
    """TCP ping. The possible results:
        * latency=x, error=False: successful TCP handshake
        * latency=x, error=True: connection failure, like TCP-RST
        * latency=-1, error=False: timeout
    """
    def __init__(self, port, *args, **kwargs):
        """Constructor.

        Args:
            port (int): TCP port to ping.
            *args (...): Arguments passed to `cping.protocols.Ping`.
            **kwargs (x=y): Keyword arguments passed to `cping.protocols.Ping`.

        Raises:
            TypeError: If `port` is not a integer.
            ValueError: If `port` is not between 1 and 65535.
        """
        self.port = port
        super().__init__(*args, **kwargs)

    @property
    def port(self):
        """TCP port to ping."""
        return self._port

    @port.setter
    def port(self, value):
        if not isinstance(value, int):
            raise TypeError('port must be an integer')

        if not 0 < value < 65536:
            raise ValueError('port outside of range 1-65535')

        self._port = value

    def ping_loop(self, host):
        try:
            host_info = socket.getaddrinfo(host=host.address,
                                           port=self.port,
                                           proto=socket.IPPROTO_TCP)[0]
        except socket.gaierror:
            host.status = 'Host resolution failed'
            return

        while True:
            latency = None
            error = False

            test_socket = socket.socket(host_info[0], host_info[1])
            test_socket.settimeout(self.interval)

            # Update the port in the host_info in case it was changed
            location = host_info[4][:1] + (self.port, ) + host_info[4][2:]
            checkpoint = time.perf_counter()

            try:
                test_socket.connect(location)
            except ConnectionError:
                # Got a response but it was an error (e.g. TCP-RST)
                error = True
            except OSError:
                # OS errors, like 'Host is down' or socket.timeout
                latency = -1

            if latency is None:
                latency = time.perf_counter() - checkpoint

            host.add_result(latency, error)
            test_socket.close()

            # Sleep until signaled to stop or the timeout expires
            if host.stop_signal.wait(self.get_timeout(latency, host)):
                break
