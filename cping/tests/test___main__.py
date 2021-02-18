"""cping tests"""
import contextlib
import io
import signal
import subprocess
import sys
import threading
import time
import unittest

import cping
import cping.__main__


class TestMain(unittest.TestCase):
    """cping.__main__.main tests."""
    def test_default_layout(self):
        """Confirm that default layout is `modern`."""
        trigger = threading.Event()

        old_call = cping.LayoutModern.__call__
        cping.LayoutModern.__call__ = lambda _: trigger.set()

        try:
            cping.__main__.main(['localhost'])
            self.assertTrue(trigger.is_set())
        finally:
            cping.LayoutModern.__call__ = old_call

    def test_interval_minimum_value(self):
        """Ensure the minimum interval value is respected."""
        output = io.StringIO()

        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(output):
                cping.__main__.main(['-i', '-1', 'localhost'])

        self.assertIn('minimum interval is', output.getvalue())

    def test_keyboard_interrupt(self):
        """Confirm that a keyboard interrupt is handled."""
        # pylint: disable=no-self-use
        def patch(*_):
            raise KeyboardInterrupt()

        old_stagger_start = cping.protocols.stagger_start
        cping.protocols.stagger_start = patch

        try:
            # KeyboardInterrupt shouldn't raise an exception or return an error
            cping.__main__.main(['localhost'])
        finally:
            cping.protocols.stagger_start = old_stagger_start

    def test_ping_icmp(self):
        """Use ICMP as the Ping class."""
        trigger = threading.Event()

        old_ping_loop = cping.PingICMP.ping_loop
        cping.PingICMP.ping_loop = lambda *_: trigger.set()

        try:
            with contextlib.redirect_stdout(None):
                cping.__main__.main(['-l', 'legacy', 'localhost'])

            # The ICMP class was called
            self.assertTrue(trigger.is_set())
        finally:
            cping.PingICMP.ping_loop = old_ping_loop

    def test_ping_tcp(self):
        """Use TCP as the Ping class."""
        trigger = threading.Event()

        old_ping_loop = cping.PingTCP.ping_loop
        cping.PingTCP.ping_loop = lambda *_: trigger.set()

        try:
            with contextlib.redirect_stdout(None):
                cping.__main__.main(['-l', 'legacy', '-p', '80', 'localhost'])

            # The TCP class was called
            self.assertTrue(trigger.is_set())
        finally:
            cping.PingTCP.ping_loop = old_ping_loop

    def test_signal_interrupt(self):
        """Sending an interrupt signal should exit gracefully."""
        process = subprocess.Popen(
            [sys.executable, '-m', 'cping', '-l', 'legacy', '127.0.0.1'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        time.sleep(0.5)
        process.send_signal(signal.SIGINT)
        process.wait(0.5)

        self.assertEqual(process.stderr.read(), b'')
        process.stderr.close()
