"""cping.protocols tests"""
import threading
import time
import unittest

import cping.protocols

# pylint: disable=protected-access, too-many-public-methods


class TestHost(unittest.TestCase):
    """cping.protocols.Host tests."""
    def test_add_result(self):
        """Add a result."""
        host = cping.protocols.Ping()('localhost')
        host.add_result(1)
        host.add_result(2, True)

        self.assertEqual(host.results[0], {'latency': 1, 'error': False})
        self.assertEqual(host.results[1], {'latency': 2, 'error': True})

    def test_add_result_lock(self):
        """Ensure add_result locks _results_lock."""
        host = cping.protocols.Ping()('localhost')

        # Adding a result requires locking
        with host._results_lock:
            thread = threading.Thread(target=host.add_result, args=(1, ))
            thread.start()
            time.sleep(0.1)

            self.assertEqual(len(host.results), 0)

        # Releasing the lock should allow the thread to change the length
        thread.join()
        self.assertEqual(len(host.results), 1)

    def test_add_result_invalid_type_latency(self):
        """Add a result with an invalid latency type."""
        host = cping.protocols.Ping()('localhost')

        with self.assertRaisesRegex(TypeError, 'latency must be a float'):
            host.add_result('hi')

    def test_add_result_invalid_type_error(self):
        """Add a result with an invalid error type."""
        host = cping.protocols.Ping()('localhost')

        with self.assertRaisesRegex(TypeError, 'error must be a boolean'):
            host.add_result(1, 1)

    def test_is_running(self):
        """Confirm that the host correctly detects when the loop is running."""
        host = cping.protocols.Ping()('localhost')
        self.assertFalse(host.is_running())

        stop = threading.Event()
        host._test_thread = threading.Thread(target=stop.wait)
        self.assertFalse(host.is_running())

        host._test_thread.start()
        self.assertTrue(host.is_running())

        stop.set()
        host._test_thread.join()
        self.assertFalse(host.is_running())

    def test_results_summary(self):
        """Get the statistics on the results."""
        host = cping.protocols.Ping()('localhost')

        # All stats are None
        for key, value in host.results_summary.items():
            self.assertIsNone(value, msg='{} is not None'.format(key))

        host.add_result(0.8)
        self.assertEqual(host.results_summary['min'], 800)
        self.assertEqual(host.results_summary['avg'], 800)
        self.assertEqual(host.results_summary['max'], 800)
        self.assertIs(host.results_summary['stdev'], None)
        self.assertEqual(host.results_summary['loss'], 0)

        host.add_result(0.6)
        self.assertEqual(host.results_summary['min'], 600)
        self.assertEqual(host.results_summary['avg'], 700)
        self.assertEqual(host.results_summary['max'], 800)
        self.assertEqual(round(host.results_summary['stdev'], 3), 141.421)
        self.assertEqual(host.results_summary['loss'], 0)

        host.add_result(-1)
        self.assertEqual(host.results_summary['min'], 600)
        self.assertEqual(host.results_summary['avg'], 700)
        self.assertEqual(host.results_summary['max'], 800)
        self.assertEqual(round(host.results_summary['stdev'], 3), 141.421)
        self.assertEqual(round(host.results_summary['loss'], 3), 0.333)

    def test_set_results_length(self):
        """Change the results length."""
        host = cping.protocols.Ping()('localhost')

        for i in range(120):
            host.add_result(i)

        self.assertEqual(len(host.results),
                         cping.protocols.RESULTS_LENGTH_MINIMUM)

        host.set_results_length(120)

        for i in range(120):
            host.add_result(i)

        self.assertEqual(len(host.results), 120)

    def test_set_results_length_lock(self):
        """Ensure set_results_length locks _results_lock."""
        host = cping.protocols.Ping()('localhost')
        host.set_results_length(150)

        for i in range(150):
            host.add_result(i)

        host._results_lock.acquire()

        # Setting the same length will not lock (no change is made)
        host.set_results_length(150)

        # Setting a different length requires locking
        thread = threading.Thread(target=host.set_results_length, args=(120, ))
        thread.start()
        time.sleep(0.1)
        self.assertEqual(len(host.results), 150)

        # Release should allow the thread to change the length
        host._results_lock.release()
        thread.join()
        self.assertEqual(len(host.results), 120)

    def test_set_results_length_invalid_type_new_length(self):
        """set_results_length with wrong new_length."""
        with self.assertRaisesRegex(TypeError, 'new_length must be an int'):
            cping.protocols.Ping()('localhost').set_results_length(10.0)

    def test_start(self):
        """Start host with a dummy ping_loop."""
        def dummy_ping_loop(host):
            time.sleep(0.1)
            host.stop_signal.set()

        host = cping.protocols.Ping()('localhost')
        host.protocol.ping_loop = dummy_ping_loop
        host.status = 'Cleared at start'

        # Confirm that start clears stop_signal
        host.stop_signal.set()
        host.start()

        self.assertIsNone(host.status)
        self.assertTrue(host.is_running())
        self.assertFalse(host.stop_signal.is_set())

        # Confirm that the stop signal is set
        host._test_thread.join()
        self.assertTrue(host.stop_signal.is_set())

    def test_start_delay(self):
        """Start host with a delay on ping_loop."""
        host = cping.protocols.Ping()('localhost')
        host.protocol.ping_loop = lambda host: host.stop_signal.set()

        host.start(delay=0.05)
        self.assertTrue(host.is_running())
        self.assertFalse(host.stop_signal.is_set())

        # Confirm that the stop signal is set
        host._test_thread.join()
        self.assertTrue(host.stop_signal.is_set())

    def test_start_invalid_type_delay(self):
        """Start host with a delay of an invalid type."""
        with self.assertRaisesRegex(TypeError, 'delay must be a float'):
            cping.protocols.Ping()('localhost').start(delay='hi')

    def test_stop(self):
        """Ensure stop sets stop_signal and, if `block=True`, waits until
        ping_loop exits."""
        def dummy_ping_loop(host):
            host.stop_signal.wait()
            time.sleep(0.1)

        host = cping.protocols.Ping()('localhost')
        host.protocol.ping_loop = dummy_ping_loop

        host.start()
        self.assertFalse(host.stop_signal.is_set())
        self.assertTrue(host._test_thread.is_alive())

        host.stop()
        self.assertTrue(host.stop_signal.is_set())
        self.assertTrue(host._test_thread.is_alive())

        host.stop(block=True)
        self.assertTrue(host.stop_signal.is_set())
        self.assertFalse(host._test_thread.is_alive())

    def test_invalid_type_address(self):
        """Create an instance of Host with an invalid host type."""
        with self.assertRaisesRegex(TypeError, 'address must be a string'):
            cping.protocols.Host(1, None)

    def test_invalid_type_protocol(self):
        """Create an instance of Host with an invalid protocol type."""
        regex = 'protocol must be an instance of cping.protocols.Ping'

        with self.assertRaisesRegex(TypeError, regex):
            cping.protocols.Host('localhost', None)

    def test_invalid_type_status(self):
        """Host's status with invalid type."""
        host = cping.protocols.Ping()('localhost')
        self.assertIs(host.status, None)

        with self.assertRaisesRegex(TypeError, 'status must be a string'):
            host.status = 1

    def test_read_only_address(self):
        """Host's address attribute is read only."""
        host = cping.protocols.Ping()('localhost')
        self.assertEqual(host.address, 'localhost')

        with self.assertRaisesRegex(AttributeError, 'can.t set attribute'):
            host.address = 'hi'

    def test_read_only_burst_mode(self):
        """Host's burst_mode attribute is read only."""
        host = cping.protocols.Ping()('localhost')
        self.assertTrue(isinstance(host.burst_mode, threading.Event))

        with self.assertRaisesRegex(AttributeError, 'can.t set attribute'):
            host.burst_mode = None

    def test_read_only_protocol(self):
        """Host's protocol attribute is read only."""
        ping = cping.protocols.Ping()
        host = cping.protocols.Host('localhost', ping)
        self.assertIs(host.protocol, ping)

        with self.assertRaisesRegex(AttributeError, 'can.t set attribute'):
            host.protocol = None

    def test_read_only_results(self):
        """Host's results attribute is read only."""
        host = cping.protocols.Ping()('localhost')

        # Confirm a copy is returned
        self.assertIsNot(host.results, host.results)

        with self.assertRaisesRegex(AttributeError, 'can.t set attribute'):
            host.results = {}

    def test___str__(self):
        """Confim Host's __str__ format."""
        self.assertEqual(str(cping.protocols.Ping()('hello')), 'hello')


class TestPing(unittest.TestCase):
    """cping.protocols.Ping tests."""
    def test_get_timeout(self):
        """Timeout should account for the test latency and burst mode."""
        host = cping.protocols.Ping()('host')

        # The latency is subtracted from the protocol interval
        self.assertEqual(host.protocol.get_timeout(0.3, host), 0.7)

        # No timeout when the ping failed (already spent the full interval)
        self.assertEqual(host.protocol.get_timeout(-1, host), 0)

        # No timeout when the burst mode is enabled
        host.burst_mode.set()
        self.assertEqual(host.protocol.get_timeout(0.3, host), 0)

    def test_ping_loop(self):
        """Ensure ping_loop raises NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            cping.protocols.Ping().ping_loop(None)

    def test_invalid_type_interval(self):
        """Create an instance of Ping with an invalid interval type."""
        with self.assertRaisesRegex(TypeError, 'interval must be a float'):
            cping.protocols.Ping('hi')


class TestStaggerStart(unittest.TestCase):
    """cping.protocols.stagger_start tests."""
    def test_timing(self):
        """Confirm three hosts are staggered over 0.6 seconds, with the first
        starting immediately, and then 0.2 before each of the two that follow."""
        ping = cping.protocols.Ping()
        ping.ping_loop = lambda _: startup_times.append(time.time())

        # Record the time at which the hosts start
        startup_fuzz = 0.1
        startup_times = []

        checkpoint = time.time()
        hosts = [ping('1'), ping('2'), ping('3')]
        cping.protocols.stagger_start(hosts, 0.6)

        # Wait for the last host to finish
        hosts[2]._test_thread.join()

        self.assertLess(startup_times[0] - checkpoint, startup_fuzz)
        self.assertLess(startup_times[1] - checkpoint, 0.2 + startup_fuzz)
        self.assertLess(startup_times[2] - checkpoint, 0.4 + startup_fuzz)
