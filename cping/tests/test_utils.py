'''cping.utils tests'''
import threading
import time
import unittest

import cping.protocols
import cping.utils

# pylint: disable=protected-access


class TestCreateSharedEvent(unittest.TestCase):
    '''cping.utils.create_stared_event tests.'''
    def test_set(self):
        '''Shared event should be set when any of the child events are set, and
        cleared when all child events are cleared.'''
        events = [threading.Event() for _ in range(3)]
        shared = cping.utils.create_shared_event(*events)

        # No events set; all are cleared at the start
        self.assertFalse(all((e.is_set() for e in events + [shared])))

        # Setting an event; shared event set
        events[0].set()
        self.assertTrue(events[0].is_set())
        self.assertFalse(events[1].is_set())
        self.assertFalse(events[2].is_set())
        self.assertTrue(shared.is_set())

        # Setting another event; shared event set
        events[1].set()
        self.assertTrue(events[0].is_set())
        self.assertTrue(events[1].is_set())
        self.assertFalse(events[2].is_set())
        self.assertTrue(shared.is_set())

        # Clearing one event; shared event set
        events[0].clear()
        self.assertFalse(events[0].is_set())
        self.assertTrue(events[1].is_set())
        self.assertFalse(events[2].is_set())
        self.assertTrue(shared.is_set())

        # Clearing the other event; shared event cleared
        events[1].clear()
        self.assertFalse(all((e.is_set() for e in events + [shared])))


class TestGenerateData(unittest.TestCase):
    '''cping.utils.generate_data tests.'''
    def test_length_gt_data(self):
        '''Length requested is greater than the data's length.'''
        data = cping.utils.generate_data(5, '123')
        self.assertEqual(data, '12312')

    def test_length_lt_data(self):
        '''Length requested is less than the data's length.'''
        data = cping.utils.generate_data(2, '123')
        self.assertEqual(data, '12')


class TestSparklinePoint(unittest.TestCase):
    '''cping.utils.sparkline_point tests.'''
    base = 0x2581

    def test_divide_by_zero(self):
        '''Return the lowest sparkline point when minimum and maximum are equal.'''
        point = cping.utils.sparkline_point(1, 1, 1)
        self.assertEqual(point, chr(self.base))

    def test_maximum(self):
        '''A value equal to maximum should return the highest sparkline point.'''
        point = cping.utils.sparkline_point(2, 1, 2)
        self.assertEqual(point, chr(self.base + 6))

    def test_minimum(self):
        '''A value equal to minimum should return the lowest sparkline point.'''
        point = cping.utils.sparkline_point(1, 1, 2)
        self.assertEqual(point, chr(self.base))

    def test_standard_deviation(self):
        '''If the standard deviation is less than the threshold, the lowest
        sparkline point is raised.'''
        point = cping.utils.sparkline_point(1, 1, 2, 0.1)
        self.assertGreater(ord(point), self.base)


class TestStaggerStart(unittest.TestCase):
    '''cping.utils.stagger_start tests.'''
    def test_timing(self):
        '''Confirm three hosts are staggered over 0.6 seconds, with the first
        starting immediately, and then 0.2 before each of the two that follow.'''
        ping = cping.protocols.Ping()
        ping.ping_loop = lambda _: startup_times.append(time.time())

        # Record the time at which the hosts start
        startup_fuzz = 0.1
        startup_times = []

        checkpoint = time.time()
        hosts = [ping('1'), ping('2'), ping('3')]
        cping.utils.stagger_start(hosts, 0.6)

        # Wait for the last host to finish
        hosts[2]._test_thread.join()

        self.assertLess(startup_times[0] - checkpoint, startup_fuzz)
        self.assertLess(startup_times[1] - checkpoint, 0.2 + startup_fuzz)
        self.assertLess(startup_times[2] - checkpoint, 0.4 + startup_fuzz)
