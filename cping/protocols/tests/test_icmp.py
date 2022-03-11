'''cping.protocols.icmp tests'''
import collections
import time
import unittest
import unittest.mock

import cping.protocols.icmp
import cping.protocols.tests


class TestPing(unittest.TestCase):
    '''cping.protocols.icmp.Ping tests.'''
    # pylint: disable=no-self-use

    def test_change_interval(self):
        '''Change the interval in the middle of the test.'''
        protocol = cping.protocols.icmp.Ping()
        cping.protocols.tests.ping_change_interval(self, protocol)

    def test_failed_resolution(self):
        '''Failed resolution.'''
        host = cping.protocols.icmp.Ping()('there.exampe.org')

        # ping_loop is blocking but will exit when the resolution fails
        host.protocol.ping_loop(host)
        self.assertEqual(host.status, 'Host resolution failed')

    def test_host_not_responding(self):
        '''Nothing is sent back.'''
        host = cping.protocols.icmp.Ping(0.2)('1.2.3.4')
        cping.protocols.tests.ping_loop_once(host)

        self.assertEqual(len(host.results), 1)
        self.assertEqual(host.results[0]['latency'], -1)

    def test_host_responding_ipv4(self):
        '''Host replying on IPv4.'''
        host = cping.protocols.icmp.Ping()('127.0.0.1')
        cping.protocols.tests.ping_loop_once(host)

        self.assertEqual(len(host.results), 1)
        self.assertNotEqual(host.results[0]['latency'], -1)

    def test_host_responding_ipv6(self):
        '''Host replying on IPv6.'''
        host = cping.protocols.icmp.Ping()('::1')
        cping.protocols.tests.ping_loop_once(host)

        self.assertEqual(len(host.results), 1)
        self.assertNotEqual(host.results[0]['latency'], -1)

    def test_late_reply(self):
        '''A response was received after it timed out.'''
        host = cping.protocols.icmp.Ping(0.0000001)('127.0.0.1')
        patch = collections.UserDict(cping.protocols.icmp.Ping.host_map)
        patch.pop = lambda *_: None

        with unittest.mock.patch('cping.protocols.icmp.Ping.host_map', patch):
            cping.protocols.tests.ping_loop_once(host)
            time.sleep(0.3)

            self.assertNotEqual(host.results[0]['latency'], -1)
            self.assertTrue(host.results[0]['error'])

    def test_malformed_packet(self):
        '''A packet that cannot be unpacked shouldn't crash the receiver thread.'''
        session = cping.protocols.icmp.Session(6)
        request = session.create_icmp_echo()
        protocol = cping.protocols.icmp.Ping()
        protocol.icmpv6_socket.sendto(request[:8], ('::1', 0))

    def test_os_error(self):
        '''Test OSError handling on `socket.sendto`.'''

        def patch(*_):
            raise OSError('Some message')

        host = cping.protocols.icmp.Ping()('127.0.0.1')

        with unittest.mock.patch('threading.Event.wait', patch):
            # ping_loop is blocking but will exit when the exception is raised
            host.protocol.ping_loop(host)
            self.assertEqual(host.status, 'Some message')

    def test_unknown_host(self):
        '''A packet with an unknown identifier should be ignored.'''
        session = cping.protocols.icmp.Session(6)
        request = session.create_icmp_echo()
        protocol = cping.protocols.icmp.Ping()
        protocol.icmpv6_socket.sendto(request, ('::1', 0))


class TestSession(unittest.TestCase):
    '''cping.protocols.icmp.Session tests.'''

    def test_get_checksum_odd_sized(self):
        '''Ensure that odd-lengthed data is padded accordingly.'''
        even = cping.protocols.icmp.Session.get_checksum(b'\x01\x02\x03\x00')
        odd = cping.protocols.icmp.Session.get_checksum(b'\x01\x02\x03')
        self.assertEqual(even, odd)
