"""Generic code for cping.protocols tests."""
import time


def ping_change_interval(test_case, protocol):
    """Change the interval in the middle of the test."""
    protocol.interval = 1

    host = protocol('1.2.3.4')
    host.start()

    time.sleep(0.5)
    protocol.interval = 0.5

    # Remainder of first probe, two full probes, and stop during the fourth
    # ----->|<----->|<----->|<---
    time.sleep(0.5 + 0.5 + 0.5 + 0.25)
    host.stop(block=True)

    test_case.assertEqual(len(host.results), 4)
