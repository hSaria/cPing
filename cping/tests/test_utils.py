"""cping.utils tests"""
import time
import unittest

import cping.protocols
import cping.utils

# pylint: disable=protected-access


class TestStaggerStart(unittest.TestCase):
    """cping.utils.stagger_start tests."""
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
        cping.utils.stagger_start(hosts, 0.6)

        # Wait for the last host to finish
        hosts[2]._test_thread.join()

        self.assertLess(startup_times[0] - checkpoint, startup_fuzz)
        self.assertLess(startup_times[1] - checkpoint, 0.2 + startup_fuzz)
        self.assertLess(startup_times[2] - checkpoint, 0.4 + startup_fuzz)
