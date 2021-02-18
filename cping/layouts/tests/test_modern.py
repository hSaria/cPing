"""cping.layouts.modern tests"""
import curses
import threading
import unittest
import unittest.mock

import cping.layouts.modern
import cping.protocols

# Regarding `list(window.mock_calls[x])[0][y]`, this is a workaround to pre-3.8


class TestLayout(unittest.TestCase):
    """cping.layouts.modern.Layout tests."""
    @staticmethod
    def wrap_curses_getch(keys):
        """Returns a callable that will return `keys` one at a time per call.
        Once the keys are exhausted, 'q' is returned."""
        key_iterator = iter(keys)

        def getch():
            try:
                return next(key_iterator)
            except StopIteration:
                return ord('q')

        return getch

    def setUp(self):
        curses.init_pair = lambda *_: None
        curses.color_pair = lambda x: x

    def test___call__(self):
        """Confirm `__call__` calls `render`."""
        layout = cping.layouts.modern.Layout(cping.protocols.Ping())
        layout.add_host('1')

        trigger = threading.Event()
        layout.render = lambda x: x.set()
        curses.wrapper = lambda x: x(trigger)

        layout()
        self.assertTrue(trigger.is_set())

    def test_initialize_colors(self):
        """Confirm `initialize_colors` populates `Layout.colors`."""
        colors = ['green', 'red', 'yellow']

        for color in colors:
            self.assertIsNone(cping.layouts.modern.Layout.colors.get(color))

        cping.layouts.modern.Layout.initialize_colors()

        for color in colors:
            self.assertIsNotNone(cping.layouts.modern.Layout.colors.get(color))

    def test_render_sparkline(self):
        """`render_sparkline` should call `window.addstr`."""
        host = cping.protocols.Ping()('localhost')
        host.add_result(-1)
        host.add_result(0.1)
        host.add_result(0.2, True)
        host.add_result(-1)

        window = unittest.mock.MagicMock()
        cping.layouts.modern.Layout.render_sparkline(window, 1, 2, host, 3)

        green = cping.layouts.modern.Layout.colors.get('green')
        red = cping.layouts.modern.Layout.colors.get('red')
        yellow = cping.layouts.modern.Layout.colors.get('yellow')

        # The first result will not fit because of the length limit
        self.assertEqual(len(window.mock_calls), 3)

        self.assertEqual(list(window.mock_calls[0])[1][0], 1)
        self.assertEqual(list(window.mock_calls[0])[1][1], 2)
        self.assertEqual(list(window.mock_calls[0])[1][3], green)

        self.assertEqual(list(window.mock_calls[1])[1][0], 1)
        self.assertEqual(list(window.mock_calls[1])[1][1], 3)
        self.assertEqual(list(window.mock_calls[1])[1][3], yellow)

        self.assertEqual(list(window.mock_calls[2])[1][0], 1)
        self.assertEqual(list(window.mock_calls[2])[1][1], 4)
        self.assertEqual(list(window.mock_calls[2])[1][3], red)

    def test_render_table(self):
        """`render_table` should call `window.erase`, `window.addnstr`, and
        `window.refresh`."""
        host1 = cping.protocols.Ping()('host1')
        host2 = cping.protocols.Ping()('host2')
        table = cping.layouts.modern.get_table([host1, host2])

        window = unittest.mock.MagicMock()
        window.getmaxyx = lambda: (24, 80)

        cping.layouts.modern.Layout.render_table(window, table, 0)

        # Erase, 4x addnstr (header, 2x host, footer), refresh
        self.assertEqual(len(window.mock_calls), 6)

        # Erase at the begining and refresh at the end
        self.assertEqual(unittest.mock.call.erase(), window.mock_calls[0])
        self.assertEqual(unittest.mock.call.refresh(), window.mock_calls[5])

        # The table is ordered correctly
        self.assertTrue(list(window.mock_calls[1])[1][2].startswith(' HOST'))
        self.assertTrue(list(window.mock_calls[2])[1][2].startswith('host1'))
        self.assertTrue(list(window.mock_calls[3])[1][2].startswith('host2'))
        self.assertTrue(list(window.mock_calls[4])[1][2].startswith(' PAGE'))

        # The header is selected
        header_attributes = list(window.mock_calls[1])[1][4]
        self.assertEqual(header_attributes & curses.A_BOLD, curses.A_BOLD)

    def test_render_table_curses_error_handling(self):
        """`render_table` should handle exceptions of `curses.error`."""
        def curses_error():
            raise curses.error()

        window = unittest.mock.MagicMock()
        window.erase = curses_error
        window.getmaxyx = lambda: (24, 80)

        cping.layouts.modern.Layout.render_table(window, [], 0)

        # The error canceled the rendering before any calls were made
        self.assertEqual(len(window.mock_calls), 0)

    def test_render(self):
        """Ensure `render` sets the timeout of the window and clears the input
        buffers after `window.getch`."""
        def getch():
            getch_trigger.wait()
            return ord('q')

        flushinp_trigger = threading.Event()
        getch_trigger = threading.Event()

        window = unittest.mock.MagicMock()
        window.getch = getch
        window.getmaxyx = lambda: (24, 80)
        curses.flushinp = flushinp_trigger.set

        layout = cping.layouts.modern.Layout(cping.protocols.Ping())
        renderer = threading.Thread(target=layout.render, args=(window, ))
        renderer.start()

        # Input buffers are flushed after `window.getch`
        self.assertFalse(flushinp_trigger.is_set())
        getch_trigger.set()
        self.assertTrue(flushinp_trigger.wait(0.5))

        # Wait for the 'q' key to get processed once `getch_trigger` is set
        renderer.join()

        # Window timeout is set to the protocol interval
        interval = layout.protocol.interval * 1000
        self.assertIn(unittest.mock.call.timeout(interval), window.mock_calls)

    def test_render_function_burst_mode(self):
        """Enable/disable burst mode on a single host."""
        layout = cping.layouts.modern.Layout(cping.protocols.Ping())
        layout.add_host('host1')
        layout.add_host('host2')

        for host in layout.hosts:
            host.burst_mode.set = unittest.mock.MagicMock()
            host.burst_mode.clear = unittest.mock.MagicMock()

        keys = [curses.KEY_DOWN, ord('b')]
        window = unittest.mock.MagicMock()
        window.getch = TestLayout.wrap_curses_getch(keys)
        window.getmaxyx = lambda: (24, 80)
        layout.render(window)

        # Both hosts are cleared, but only host1 would've been set
        self.assertTrue(layout.hosts[0].burst_mode.set.called)
        self.assertFalse(layout.hosts[1].burst_mode.set.called)
        self.assertTrue(layout.hosts[0].burst_mode.clear.called)
        self.assertTrue(layout.hosts[1].burst_mode.clear.called)

    def test_render_function_burst_mode_all(self):
        """Enable/disable burst mode on all hosts."""
        layout = cping.layouts.modern.Layout(cping.protocols.Ping())
        layout.add_host('host1')
        layout.add_host('host2')

        for host in layout.hosts:
            host.burst_mode.set = unittest.mock.MagicMock()
            host.burst_mode.clear = unittest.mock.MagicMock()

        window = unittest.mock.MagicMock()
        window.getch = TestLayout.wrap_curses_getch([])
        window.getmaxyx = lambda: (24, 80)
        layout.render(window)

        # If no function matched, the default will clear burst mode
        for host in layout.hosts:
            self.assertTrue(host.burst_mode.clear.called)
            host.burst_mode.clear.reset_mock()
            self.assertFalse(host.burst_mode.clear.called)

        window.getch = TestLayout.wrap_curses_getch([ord('b')])
        layout.render(window)

        # Burst mode will be cleared at the end
        for host in layout.hosts:
            self.assertTrue(host.burst_mode.set.called)
            self.assertTrue(host.burst_mode.clear.called)

    def test_render_function_change_selection(self):
        """Ensure the selection changes but doesn't go out of the table bounds."""
        layout = cping.layouts.modern.Layout(cping.protocols.Ping())
        layout.add_host('1')

        keys = [curses.KEY_DOWN, curses.KEY_DOWN, curses.KEY_UP, curses.KEY_UP]
        window = unittest.mock.MagicMock()
        window.getch = TestLayout.wrap_curses_getch(keys)

        old_render_table = cping.layouts.modern.Layout.render_table
        cping.layouts.modern.Layout.render_table = unittest.mock.MagicMock()

        try:
            layout.render(window)
            calls = cping.layouts.modern.Layout.render_table.call_args_list
        finally:
            cping.layouts.modern.Layout.render_table = old_render_table

        # Startup table render (selection at 0). Key down twice, but selection
        # at 1; reached bottom. Key up twice, but selection at 0; reached top
        for call, selection in zip(calls, [0, 1, 1, 0, 0]):
            self.assertEqual(list(call)[0][2], selection)

    def test_render_function_sort(self):
        """Ensure accepted sort keys are between 0 and 6."""
        layout = cping.layouts.modern.Layout(cping.protocols.Ping())

        keys = [ord(str(x)) for x in range(7)]
        window = unittest.mock.MagicMock()
        window.getch = TestLayout.wrap_curses_getch(keys)
        window.getmaxyx = lambda: (24, 80)

        old_get_table_sort_key = cping.layouts.modern.get_table_sort_key
        cping.layouts.modern.get_table_sort_key = unittest.mock.MagicMock()

        try:
            layout.render(window)
            calls = cping.layouts.modern.get_table_sort_key.call_args_list
        finally:
            cping.layouts.modern.get_table_sort_key = old_get_table_sort_key

        # Sort key 7 is ignored
        for call, sort_key in zip(calls, range(6)):
            self.assertEqual(list(call)[0][0], sort_key)

    def test_render_function_start_stop(self):
        """Start/stop a single host."""
        layout = cping.layouts.modern.Layout(cping.protocols.Ping())
        layout.add_host('host1')
        layout.add_host('host2')

        for host in layout.hosts:
            host.start = unittest.mock.MagicMock()
            host.stop = unittest.mock.MagicMock()

        keys = [curses.KEY_DOWN, ord('s')]
        window = unittest.mock.MagicMock()
        window.getch = TestLayout.wrap_curses_getch(keys)
        window.getmaxyx = lambda: (24, 80)
        layout.render(window)

        # Only host1 should be started
        self.assertTrue(layout.hosts[0].start.called)
        self.assertFalse(layout.hosts[1].start.called)

        # Mark the hosts as running
        for host in layout.hosts:
            host.is_running = unittest.mock.MagicMock(return_value=True)

        window.getch = TestLayout.wrap_curses_getch(keys)
        layout.render(window)

        # Only host1 should be stopped
        self.assertTrue(layout.hosts[0].stop.called)
        self.assertFalse(layout.hosts[1].stop.called)

    def test_render_function_start_stop_all(self):
        """Start/stop all hosts."""
        layout = cping.layouts.modern.Layout(cping.protocols.Ping())
        layout.add_host('host1')
        layout.add_host('host2')

        for host in layout.hosts:
            host.start = unittest.mock.MagicMock()
            host.stop = unittest.mock.MagicMock()

        window = unittest.mock.MagicMock()
        window.getch = TestLayout.wrap_curses_getch([ord('s')])
        window.getmaxyx = lambda: (24, 80)
        layout.render(window)

        # Hosts were not running; should be started
        for host in layout.hosts:
            self.assertTrue(host.start.called)

        # Mark the hosts as running
        for host in layout.hosts:
            host.is_running = unittest.mock.MagicMock(return_value=True)

        window.getch = TestLayout.wrap_curses_getch([ord('s')])
        layout.render(window)

        # Hosts were running; should be stopped
        for host in layout.hosts:
            self.assertTrue(host.stop.called)


class TestGetHostColumns(unittest.TestCase):
    """cping.layouts.modern.get_host_columns tests."""
    def test_no_results(self):
        """A host with no results should return place-holders in the stats."""
        host = cping.protocols.Ping()('hi')

        columns = cping.layouts.modern.get_host_columns(host)
        expected = ['hi'] + (['-  '] * 5)

        self.assertEqual(columns, expected)

    def test_results(self):
        """Stats should have 2 decimal places, or a percentage for `loss`."""
        host = cping.protocols.Ping()('hi')
        host.add_result(-1)
        host.add_result(0.1)
        host.add_result(0.2)
        host.add_result(0.3)

        columns = cping.layouts.modern.get_host_columns(host)
        expected = ['hi', '100.00', '200.00', '300.00', '100.00', '25% ']

        self.assertEqual(columns, expected)


class TestGetTablePage(unittest.TestCase):
    """cping.layouts.modern.get_table_page tests."""
    def test_single_page(self):
        """A page size that shows the entire table."""
        table = list(range(10))
        size = 10
        selection = 5
        page = cping.layouts.modern.get_table_page(table, size, selection)

        self.assertEqual(page, table)

    def test_multiple_page(self):
        """A size smaller than the table length should paginate."""
        table = list(range(10))
        size = 3
        selection = 5
        page = cping.layouts.modern.get_table_page(table, size, selection)

        self.assertEqual(page, table[3:6])


class TestGetTable(unittest.TestCase):
    """cping.layouts.modern.get_table tests."""
    def test_column_width(self):
        """The columns should all have equal lengths among the rows."""
        hosts = [cping.protocols.Ping()(str(x)) for x in range(3)]
        table = cping.layouts.modern.get_table(hosts)

        hosts[0].add_result(1000)

        for index, column in enumerate(table[0]['columns']):
            column_width = len(column)

            for row in table:
                self.assertEqual(len(row['columns'][index]), column_width)

    def test_header(self):
        """Confirm the table starts with the header."""
        hosts = [cping.protocols.Ping()(str(x)) for x in range(3)]
        table = cping.layouts.modern.get_table(hosts)
        header = ['HOST', 'MIN', 'AVG', 'MAX', 'STDEV', 'LOSS']

        self.assertEqual(len(table), len(hosts) + 1)
        self.assertEqual(table[0]['line'].split(), header)

    def test_host_running(self):
        """A running host should have different attributes than a stopped one."""
        host1 = cping.protocols.Ping()('1')
        host2 = cping.protocols.Ping()('2')

        trigger = threading.Event()
        host1.protocol.ping_loop = lambda _: trigger.wait()
        host1.start()

        table = cping.layouts.modern.get_table([host1, host2])
        trigger.set()

        self.assertNotEqual(table[1]['attrs'], table[2]['attrs'])

    def test_host_status(self):
        """Host status should be included in the table."""
        host = cping.protocols.Ping()('1')
        host.status = 'Some status'
        table = cping.layouts.modern.get_table([host])

        self.assertIn(host.status, table[1]['line'])


class TestGetTableSortKey(unittest.TestCase):
    """cping.layouts.modern.get_table_sort_key tests."""
    def test_cycle(self):
        """Sorting key should cylce between asc->desc->none->asc->..."""
        self.assertEqual(cping.layouts.modern.get_table_sort_key(1, None), 1)
        self.assertEqual(cping.layouts.modern.get_table_sort_key(1, 1), -1)
        self.assertEqual(cping.layouts.modern.get_table_sort_key(1, -1), None)

    def test_different_leads_to_ascending(self):
        """Different sorting key than current leads to ascending of the new key."""
        self.assertEqual(cping.layouts.modern.get_table_sort_key(2, 1), 2)
        self.assertEqual(cping.layouts.modern.get_table_sort_key(2, -1), 2)


class TestSortHosts(unittest.TestCase):
    """cping.layouts.modern.sort_hosts tests."""
    def setUp(self):
        # min=1000, avg=2000, max=3000, stdev=1000, loss=0.0
        self.host1 = cping.protocols.Ping()('host1')
        self.host1.add_result(1)
        self.host1.add_result(2)
        self.host1.add_result(3)

        # min=3000, avg=3500, max=4000, stdev=707.10, loss=0.33
        self.host2 = cping.protocols.Ping()('host22')
        self.host2.add_result(3)
        self.host2.add_result(4)
        self.host2.add_result(-1)

        # min=500, avg=700, max=900, stdev=200, loss=0.25
        self.host3 = cping.protocols.Ping()('host3')
        self.host3.add_result(0.5)
        self.host3.add_result(0.7)
        self.host3.add_result(0.9)
        self.host3.add_result(-1)

    def test_no_results(self):
        """Sorting with a host that has no results."""
        empty_host = cping.protocols.Ping()('host3')
        hosts = [self.host1, empty_host, self.host2]

        sorted_hosts = cping.layouts.modern.sort_hosts(hosts, 2)
        self.assertEqual(sorted_hosts, [self.host1, self.host2, empty_host])

        sorted_hosts = cping.layouts.modern.sort_hosts(hosts, -2)
        self.assertEqual(sorted_hosts, [empty_host, self.host2, self.host1])

    def test_no_sorting(self):
        """Sorting key 0, or an invalid key, will not change the order."""
        hosts = [self.host3, self.host1, self.host2]

        sorted_hosts = cping.layouts.modern.sort_hosts(hosts, 0)
        self.assertEqual(sorted_hosts, [self.host3, self.host1, self.host2])

        sorted_hosts = cping.layouts.modern.sort_hosts(hosts, None)
        self.assertEqual(sorted_hosts, [self.host3, self.host1, self.host2])

        sorted_hosts = cping.layouts.modern.sort_hosts(hosts, 7)
        self.assertEqual(sorted_hosts, [self.host3, self.host1, self.host2])

    def test_sorting_host(self):
        """Sorting key 1 will sort by str(host)."""
        hosts = [self.host3, self.host1, self.host2]

        sorted_hosts = cping.layouts.modern.sort_hosts(hosts, 1)
        self.assertEqual(sorted_hosts, [self.host1, self.host3, self.host2])

        sorted_hosts = cping.layouts.modern.sort_hosts(hosts, -1)
        self.assertEqual(sorted_hosts, [self.host2, self.host3, self.host1])

    def test_sorting_min(self):
        """Sorting key 2 will sort by the minimum statistic."""
        hosts = [self.host1, self.host2, self.host3]

        sorted_hosts = cping.layouts.modern.sort_hosts(hosts, 2)
        self.assertEqual(sorted_hosts, [self.host3, self.host1, self.host2])

        sorted_hosts = cping.layouts.modern.sort_hosts(hosts, -2)
        self.assertEqual(sorted_hosts, [self.host2, self.host1, self.host3])

    def test_sorting_max(self):
        """Sorting key 3 will sort by the maximum statistic."""
        hosts = [self.host1, self.host2, self.host3]

        sorted_hosts = cping.layouts.modern.sort_hosts(hosts, 3)
        self.assertEqual(sorted_hosts, [self.host3, self.host1, self.host2])

        sorted_hosts = cping.layouts.modern.sort_hosts(hosts, -3)
        self.assertEqual(sorted_hosts, [self.host2, self.host1, self.host3])

    def test_sorting_avg(self):
        """Sorting key 4 will sort by the average statistic."""
        hosts = [self.host1, self.host2, self.host3]

        sorted_hosts = cping.layouts.modern.sort_hosts(hosts, 4)
        self.assertEqual(sorted_hosts, [self.host3, self.host1, self.host2])

        sorted_hosts = cping.layouts.modern.sort_hosts(hosts, -4)
        self.assertEqual(sorted_hosts, [self.host2, self.host1, self.host3])

    def test_sorting_stdev(self):
        """Sorting key 5 will sort by the standard deviation statistic."""
        hosts = [self.host3, self.host1, self.host2]

        sorted_hosts = cping.layouts.modern.sort_hosts(hosts, 5)
        self.assertEqual(sorted_hosts, [self.host3, self.host2, self.host1])

        sorted_hosts = cping.layouts.modern.sort_hosts(hosts, -5)
        self.assertEqual(sorted_hosts, [self.host1, self.host2, self.host3])

    def test_sorting_loss(self):
        """Sorting key 6 will sort by the packet loss statistic."""
        hosts = [self.host3, self.host1, self.host2]

        sorted_hosts = cping.layouts.modern.sort_hosts(hosts, 6)
        self.assertEqual(sorted_hosts, [self.host1, self.host3, self.host2])

        sorted_hosts = cping.layouts.modern.sort_hosts(hosts, -6)
        self.assertEqual(sorted_hosts, [self.host2, self.host3, self.host1])


class TestSparklinePoint(unittest.TestCase):
    """cping.layouts.modern.sparkline_point tests."""
    base = 0x2581

    def test_divide_by_zero(self):
        """Return the lowest sparkline point when minimum and maximum are equal."""
        point = cping.layouts.modern.sparkline_point(1, 1, 1)
        self.assertEqual(point, chr(self.base))

    def test_maximum(self):
        """A value equal to maximum should return the highest sparkline point."""
        point = cping.layouts.modern.sparkline_point(2, 1, 2)
        self.assertEqual(point, chr(self.base + 6))

    def test_minimum(self):
        """A value equal to minimum should return the lowest sparkline point."""
        point = cping.layouts.modern.sparkline_point(1, 1, 2)
        self.assertEqual(point, chr(self.base))

    def test_standard_deviation(self):
        """If the standard deviation is less than the threshold, the lowest
        sparkline point is raised."""
        point = cping.layouts.modern.sparkline_point(1, 1, 2, 0.1)
        self.assertGreater(ord(point), self.base)
