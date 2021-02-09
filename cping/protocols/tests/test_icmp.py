"""cping.protocols.icmp tests"""
import unittest

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


class TestGetChecksum(unittest.TestCase):
    """cping.protocols.icmp.get_checksum tests."""
    def test_odd_sized(self):
        """Ensure that odd-lengthed data is padded accordingly."""
        even_checksum = cping.protocols.icmp.get_checksum(b'\x01\x02\x03\x00')
        odd_checksum = cping.protocols.icmp.get_checksum(b'\x01\x02\x03')
        self.assertEqual(even_checksum, odd_checksum)


class TestGenerateData(unittest.TestCase):
    """cping.protocols.icmp.generate_data tests."""
    def test_loop_data(self):
        """Loop data until length."""
        self.assertEqual(cping.protocols.icmp.generate_data(5, '123'), '12312')
