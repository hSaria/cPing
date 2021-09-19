'''cping.__main__ tests'''
import contextlib
import io
import signal
import subprocess
import sys
import threading
import time
import unittest
import unittest.mock

import cping
import cping.__main__
import cping.utils


class TestMain(unittest.TestCase):
    '''cping.__main__.main tests.'''
    def test_default_layout(self):
        '''Confirm that default layout is `modern`.'''
        trigger = threading.Event()
        patch = lambda _: trigger.set()

        with unittest.mock.patch('cping.LayoutModern.__call__', patch):
            cping.__main__.main(['localhost'])
            self.assertTrue(trigger.is_set())

    def test_help_layout(self):
        '''Layout should not be present in the help when ran on Windows.'''
        with unittest.mock.patch('sys.platform', 'darwin'):
            output = io.StringIO()

            with self.assertRaises(SystemExit):
                with contextlib.redirect_stdout(output):
                    cping.__main__.main(['-h'])

            self.assertIn('--layout', output.getvalue())

        with unittest.mock.patch('sys.platform', 'win32'):
            output = io.StringIO()

            with self.assertRaises(SystemExit):
                with contextlib.redirect_stdout(output):
                    cping.__main__.main(['-h'])

            self.assertNotIn('--layout', output.getvalue())

    def test_interval_minimum_value(self):
        '''Ensure the minimum interval value is respected.'''
        output = io.StringIO()

        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(output):
                cping.__main__.main(['-i', '-1', 'localhost'])

        self.assertIn('minimum interval is', output.getvalue())

    def test_keyboard_interrupt(self):
        '''Confirm that a keyboard interrupt is handled.'''
        def patch(*_):
            raise KeyboardInterrupt()

        with unittest.mock.patch('cping.utils.stagger_start', patch):
            try:
                cping.__main__.main(['localhost'])
            except KeyboardInterrupt:  # pragma: no cover
                self.fail('KeyboardInterrupt not caught by main')

    def test_ping_icmp(self):
        '''Use ICMP as the Ping class.'''
        trigger = threading.Event()
        patch = lambda *_: trigger.set()

        with unittest.mock.patch('cping.PingICMP.ping_loop', patch):
            with contextlib.redirect_stdout(None):
                cping.__main__.main(['-l', 'legacy', 'localhost'])

            # The ICMP class was called
            self.assertTrue(trigger.is_set())

    def test_ping_tcp(self):
        '''Use TCP as the Ping class.'''
        trigger = threading.Event()
        patch = lambda *_: trigger.set()

        with unittest.mock.patch('cping.PingTCP.ping_loop', patch):
            with contextlib.redirect_stdout(None):
                cping.__main__.main(['-l', 'legacy', '-p', '80', 'localhost'])

            # The TCP class was called
            self.assertTrue(trigger.is_set())

    def test_signal_interrupt(self):
        '''Sending an interrupt signal should exit gracefully.'''
        args = [sys.executable, '-m', 'cping', '-l', 'legacy', '127.0.0.1']

        with subprocess.Popen(args=args,
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.PIPE) as process:
            time.sleep(0.5)
            process.send_signal(signal.SIGINT)
            process.wait(0.5)

            self.assertEqual(process.stderr.read(), b'')
