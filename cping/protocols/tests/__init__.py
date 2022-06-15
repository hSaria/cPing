'''Generic code for cping.protocols tests.'''
import socket
import time
import unittest.mock


def resolve_failed(test_case, protocol):
    '''Assert failed host resolution is handled gracefully.'''
    host = protocol('there.exampe.org')

    def patch(*_1, **_2):
        raise socket.gaierror

    with unittest.mock.patch('socket.getaddrinfo', patch):
        # ping_loop is blocking but will exit when the resolution fails
        host.protocol.ping_loop(host)

    test_case.assertEqual(host.status, 'Host resolution failed')


def ping_change_interval(test_case, protocol):
    '''Change the interval in the middle of the test.'''
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
    '''Start the host and run a single iteration.'''
    old_wait = host.wait

    try:
        host.wait = lambda *_: host.stop_signal.set()
        host.start()
        host.stop_signal.wait()
        host.stop_signal.clear()
    finally:
        host.wait = old_wait
