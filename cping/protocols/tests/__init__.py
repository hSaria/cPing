"""Generic code for cping.protocols tests."""
import time


def ping_change_interval(test_case, protocol):
    """Change the interval in the middle of the test."""
    protocol.interval = 0.5

    host = protocol('1.2.3.4')
    host.start()

    # Change the interval in the middle of the first probe (takes effect after)
    time.sleep(protocol.interval / 2)
    protocol.interval = protocol.interval / 2

    # Remainder of first probe, one full probe, and stop during the third
    # ----->|<----->|<---
    time.sleep(protocol.interval * 2.5)
    host.stop(block=True)

    test_case.assertEqual(len(host.results), 3)


def ping_loop_once(host):
    """Start the host and run a single iteration."""
    host.protocol.wait = lambda *_: host.stop_signal.set()
    host.start()
    host.stop_signal.wait()
    host.stop_signal.clear()
