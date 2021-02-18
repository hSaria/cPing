"""Generic code and base classes for ping protocols."""
import collections
import statistics
import threading
import time

# Lower bound on the number of results
RESULTS_LENGTH_MINIMUM = 50


class Host:
    """A destination of pings of which it stores the results."""

    # pylint: disable=too-many-instance-attributes
    def __init__(self, address, protocol):
        """Constructor.

        Args:
            address (str): Ping destination.
            protocol (cping.protocols.Ping): Protocol to use for pinging.

        Raises:
            TypeError: If `address` is not a string. If protocol is not an
                instance of `cping.protocols.Ping`
        """
        if not isinstance(address, str):
            raise TypeError('address must be a string')

        if not isinstance(protocol, Ping):
            raise TypeError('protocol must be an instance of '
                            'cping.protocols.Ping')

        self._address = address
        self._burst_mode = threading.Event()
        self._protocol = protocol
        self._results = collections.deque(maxlen=RESULTS_LENGTH_MINIMUM)
        self._results_lock = threading.Lock()
        self._results_summary = None
        self._status = None
        self._stop_signal = threading.Event()
        self._test_thread = None

    def __str__(self):
        return self._address

    @property
    def address(self):
        """Ping destination."""
        return self._address

    @property
    def burst_mode(self):
        """An instance of `threading.Event` to use burst mode when set."""
        return self._burst_mode

    @property
    def protocol(self):
        """A reference to the Ping object the host is using."""
        return self._protocol

    @property
    def results(self):
        """A `collections.deque` containing results, each as a dictionary of
            * latency (float): the latency of a ping probe (-1 for no reply)
            * error (bool): whether the ping reply was an error (e.g. TCP-RST)
        """
        return self._results.copy()

    @property
    def results_summary(self):
        """Dictionary containing the following statistics (float):
            * Minimum (min)
            * Average (avg)
            * Maximum (max)
            * Standard deviation (stdev)
            * Packet loss percentage (loss)

        Depending on the number of results, some may be `None`. The unit is ms.
        """
        if self._results_summary is not None:
            return self._results_summary

        summary = {
            'min': None,
            'avg': None,
            'max': None,
            'stdev': None,
            'loss': None,
        }

        # Remove failed pings and only get the delay value
        results = [x['latency'] for x in self.results if x['latency'] != -1]

        if results:
            summary['min'] = min(results) * 1000
            summary['avg'] = statistics.mean(results) * 1000
            summary['max'] = max(results) * 1000
            summary['loss'] = (1 - (len(results) / len(self.results)))

            if len(results) > 1:
                summary['stdev'] = statistics.stdev(results) * 1000

        self._results_summary = summary
        return summary

    @property
    def status(self):
        """String describing the status of the host."""
        return self._status

    @status.setter
    def status(self, value):
        if not isinstance(value, str):
            raise TypeError('status must be a string')

        self._status = value

    @property
    def stop_signal(self):
        """Instance of `threading.Event` to signal to the test to stop."""
        return self._stop_signal

    def add_result(self, latency, error=False):
        """Adds a result (a float that represents the latency of a ping reply).

        Args:
            latency (float): Latency between the ping request and its reply.
            error (bool): Whether the reply is an error, like a TCP-RST when the
                port is not open.

        Raises:
            TypeError: If `latency` is not a float. If `error` is not a boolean.
        """
        if not isinstance(latency, (float, int)):
            raise TypeError('latency must be a float')

        if not isinstance(error, bool):
            raise TypeError('error must be a boolean')

        with self._results_lock:
            self._results.append({'latency': latency, 'error': error})
            self._results_summary = None

    def is_running(self):
        """Returns `True` if the test is running. Otherwise, `False`."""
        return self._test_thread is not None and self._test_thread.is_alive()

    def set_results_length(self, new_length):
        """Changes the results maximum length to be `new_length`.

        Args:
            new_length (int): The new maximum length of the results.

        Raises:
            TypeError: If `new_length` is not an integer.
        """
        if not isinstance(new_length, int):
            raise TypeError('new_length must be an integer')

        new_length = max(new_length, RESULTS_LENGTH_MINIMUM)

        # Already at new length
        if self._results.maxlen == new_length:
            return

        # Lock to prevent result loss while the new deque replaces the old one
        with self._results_lock:
            # Create deque with the new length
            self._results = collections.deque(self._results, maxlen=new_length)

    def start(self, delay=0):
        """Clears `self.status` and starts the ping loop.

        Args:
            * delay (float): Delay before the ping loop starts.

        Raises:
            TypeError: If `delay` is not a float.
        """
        if not isinstance(delay, (float, int)):
            raise TypeError('delay must be a float')

        def ping_loop_wrapper():
            time.sleep(delay)
            self._protocol.ping_loop(self)

        self._status = None
        self.stop_signal.clear()

        if not self.is_running():
            self._test_thread = threading.Thread(target=ping_loop_wrapper)
            self._test_thread.start()

    def stop(self, block=False):
        """Signals the ping loop to stop.

        Args:
            * block (bool): Whether to block until the ping loop stops.
        """
        self.stop_signal.set()
        if block:
            self._test_thread.join()


class Ping:
    """A ping base class. Subclasses must implement `ping_loop`."""
    def __init__(self, interval=1):
        """Constructor.

        Args:
            interval (float): Seconds, of a fraction thereof, between pings.

        Raises:
            TypeError: If `interval` is not a float.
        """
        self.interval = interval

    def __call__(self, address):
        """Returns `cping.protocols.Host(address, self)`.

        Args:
            address (str): Ping destination.
        """
        return Host(address, self)

    @property
    def interval(self):
        """Seconds, of a fraction thereof, between pings."""
        return self._interval

    @interval.setter
    def interval(self, value):
        if not isinstance(value, (float, int)):
            raise TypeError('interval must be a float')

        self._interval = value

    def get_timeout(self, latency, host):
        """Returns a float indicating the time to wait before the next ping based
        on the previous result.

        Args:
            latency (float): The latency of the previous ping.
            host (cping.protocols.Host): The test's host.
        """
        # No timeout if test failed or burst mode is enabled
        if latency == -1 or host.burst_mode.is_set():
            return 0

        # Account for the latency of the previous test
        return self.interval - latency

    def ping_loop(self, host):
        """A blocking call that will begin pinging the host and registering the
        results using `host.add_result`. An implementation must account for
        changes in protocol attributes (e.g. interval) while the loop is running.
        The loop should break when `host.stop_signal` is set.

        Args:
            host (cping.protocols.Host): The host instance to ping.
        """
        raise NotImplementedError('cping.protocols.Ping is a base class; it '
                                  'does not implement ping_loop')


def stagger_start(hosts, interval):
    """Start the hosts over the duration of an interval. For instance, three
    hosts are staggered over an interval like so:
    interval: |-------||-------||-------|
    first:    |---1--->|---1--->|---1--->
    second:      |---2--->|---2--->|---2--->
    third:          |---3--->|---3--->|---3--->
    """
    stagger_interval = interval / len(hosts)

    for index, host in enumerate(hosts):
        host.start(delay=stagger_interval * index)
