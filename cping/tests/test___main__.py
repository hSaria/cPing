"""cping tests"""
import contextlib
import io
import signal
import subprocess
import sys
import time
import threading
import unittest

import cping
import cping.__main__

# pylint: disable=protected-access


class TestStartHostsStaggered(unittest.TestCase):
    """cping.__main__.start_hosts_staggered tests."""
    def test_timing(self):
        """Confirm three hosts are staggered over 0.6 seconds, with the first
        starting immediately, and then 0.2 before each of the two that follow."""
        ping = cping.PingICMP()
        ping.ping_loop = lambda _: startup_times.append(time.time())

        # Record the time at which the hosts start
        startup_fuzz = 0.1
        startup_times = []

        checkpoint = time.time()
        hosts = [ping('1'), ping('2'), ping('3')]
        cping.__main__.start_hosts_staggered(hosts, 0.6)

        # Wait for the last host to finish
        hosts[2]._test_thread.join()

        self.assertLess(startup_times[0] - checkpoint, startup_fuzz)
        self.assertLess(startup_times[1] - checkpoint, 0.2 + startup_fuzz)
        self.assertLess(startup_times[2] - checkpoint, 0.4 + startup_fuzz)


class TestMain(unittest.TestCase):
    """cping.__main__.main tests."""
    def test_interval_minimum_value(self):
        """Ensure the minimum interval value is respected."""
        output = io.StringIO()

        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(output):
                cping.__main__.main(['-i', '-1', 'localhost'])

        self.assertIn('minimum interval is', output.getvalue())

    def test_ping_icmp(self):
        """Use ICMP as the Ping class."""
        trigger = threading.Event()
        cping.PingICMP.ping_loop = lambda *_: trigger.set()

        with contextlib.redirect_stdout(None):
            cping.__main__.main(['localhost'])

        # The ICMP class was called
        self.assertTrue(trigger.is_set())

    def test_ping_tcp(self):
        """Use TCP as the Ping class."""
        trigger = threading.Event()
        cping.PingTCP.ping_loop = lambda *_: trigger.set()

        with contextlib.redirect_stdout(None):
            cping.__main__.main(['-p', '80', 'localhost'])

        # The ICMP class was called
        self.assertTrue(trigger.is_set())

    def test_ping_tcp_invalid_port(self):
        """Supply an invalid port to TCP."""
        error = cping.__main__.main(['-p', '123456', 'localhost'])
        self.assertIsNotNone(error)

    def test_signal_interrupt(self):
        """Sending an interrupt signal should exit gracefully."""
        process = subprocess.Popen(
            [sys.executable, '-m', 'cping', '127.0.0.1'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        time.sleep(0.5)
        process.send_signal(signal.SIGINT)
        process.wait(0.5)

        self.assertEqual(process.stderr.read(), b'')
        process.stderr.close()
