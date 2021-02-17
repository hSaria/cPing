"""cping.layouts.legacy tests"""
import contextlib
import io
import re
import threading
import unittest

import cping.layouts.legacy
import cping.protocols


class TestLayout(unittest.TestCase):
    """cping.layouts.legacy.Layout tests."""
    def test___call__(self):
        """Ensure calling layout properly enters and exits the alternate buffer.
        The layout should automatically exit when no hosts are running."""
        exit_signal = threading.Event()

        layout = cping.layouts.legacy.Layout(cping.protocols.Ping(0.5))
        layout.protocol.ping_loop = lambda _: exit_signal.wait()
        layout.add_host('host1').start()
        layout.add_host('host2').start()

        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            layout_thread = threading.Thread(target=layout)
            layout_thread.start()
            exit_signal.set()
            layout_thread.join()

        # Enter alternate buffer and move to 1;1
        self.assertTrue(output.getvalue().startswith('\x1b[?1049h\x1b[H'))

        # Exit alternate buffer
        self.assertIn('\x1b[?1049l', output.getvalue())


class TestFormatHost(unittest.TestCase):
    """cping.layouts.legacy.format_host tests."""
    def test_host_status(self):
        """The host's status, if set, should be shown."""
        host = cping.protocols.Ping()('localhost')
        host.status = 'Test status'

        line = cping.layouts.legacy.format_host(host, 4, 80)
        self.assertIn(host.status, line)

    def test_line_width(self):
        """The line-width should update the host's results length."""
        host = cping.protocols.Ping()('localhost')
        old_length = host.results.maxlen

        cping.layouts.legacy.format_host(host, 4, 150)
        self.assertGreater(host.results.maxlen, old_length)

    def test_results_histogram(self):
        """Ensure the results are correctly represented."""
        host = cping.protocols.Ping()('localhost')

        for result in [-1, 0, -1, -1, 0]:
            host.add_result(result)

        line = cping.layouts.legacy.format_host(host, 4, 80)
        self.assertIn('.!..!', strip_colors(line))


class TestGetColor(unittest.TestCase):
    """cping.layouts.legacy.get_color tests."""
    def test_color(self):
        """Get the ANSI code for a color"""
        self.assertEqual(cping.layouts.legacy.get_color('red'), '\x1b[31m')

    def test_last_color(self):
        """Getting a color that is the last color should return an empty string."""
        self.assertEqual(cping.layouts.legacy.get_color('red', 'red'), '')

    def test_non_existent_color(self):
        """A non-existent color should return an empty string"""
        self.assertEqual(cping.layouts.legacy.get_color('hi'), '')


class TestGetTable(unittest.TestCase):
    """cping.layouts.legacy.get_table tests."""
    def test_overflow(self):
        """Create a table with too many hosts to ensure they don't overflow."""
        hosts = [cping.protocols.Ping()(str(x)) for x in range(60)]

        table = cping.layouts.legacy.get_table(hosts)
        self.assertIn(' more', table)

        table = cping.layouts.legacy.get_table(hosts, all_hosts=True)
        self.assertNotIn(' more', table)


def strip_colors(data):
    """Remove the ANSI foreground colors from the string `data`."""
    return re.sub(r'\x1b\[\d*m', '', data)
