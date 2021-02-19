"""cping.protocols.icmp tests"""
import unittest
import unittest.mock

import cping.protocols.icmp
import cping.protocols.tests


class TestPing(unittest.TestCase):
    """cping.protocols.icmp.Ping tests."""
    def test_change_interval(self):
        """Change the interval in the middle of the test."""
        protocol = cping.protocols.icmp.Ping()
        cping.protocols.tests.ping_change_interval(self, protocol)

    def test_failed_resolution(self):
        """Failed resolution."""
        host = cping.protocols.icmp.Ping()('there.exampe.org')

        # ping_loop is blocking but will exit when the resolution fails
        host.protocol.ping_loop(host)
        self.assertEqual(host.status, 'Host resolution failed')

    def test_host_not_responding(self):
        """Nothing is sent back."""
        host = cping.protocols.icmp.Ping(0.2)('1.2.3.4')
        host.start()
        host.stop(block=True)

        self.assertEqual(len(host.results), 1)
        self.assertEqual(host.results[0]['latency'], -1)

    def test_host_responding_ipv4(self):
        """Host replying on IPv4."""
        host = cping.protocols.icmp.Ping()('127.0.0.1')
        host.start()
        host.stop(block=True)

        self.assertEqual(len(host.results), 1)
        self.assertNotEqual(host.results[0]['latency'], -1)

    def test_host_responding_ipv6(self):
        """Host replying on IPv6."""
        host = cping.protocols.icmp.Ping()('::1')
        host.start()
        host.stop(block=True)

        self.assertEqual(len(host.results), 1)
        self.assertNotEqual(host.results[0]['latency'], -1)

    def test_os_error(self):
        """Test OSError handling on `socket.sendto`."""
        def patch(*_):
            raise OSError('Some message')

        host = cping.protocols.icmp.Ping()('127.0.0.1')

        with unittest.mock.patch('threading.Event.wait', patch):
            # ping_loop is blocking but will exit when the exception is raised
            host.protocol.ping_loop(host)
            self.assertEqual(host.status, 'Some message')


class TestSession(unittest.TestCase):
    """cping.protocols.icmp.Session tests."""
    def test_get_checksum_odd_sized(self):
        """Ensure that odd-lengthed data is padded accordingly."""
        even = cping.protocols.icmp.Session.get_checksum(b'\x01\x02\x03\x00')
        odd = cping.protocols.icmp.Session.get_checksum(b'\x01\x02\x03')
        self.assertEqual(even, odd)

    def test__generate_data(self):
        """Loop data until length."""
        data = cping.protocols.icmp.Session.generate_data(5, '123')
        self.assertEqual(data, '12312')
