"""cping.layouts tests"""
import unittest

import cping.layouts
import cping.protocols

# pylint: disable=protected-access


class TestLayout(unittest.TestCase):
    """cping.layouts.Layout tests."""
    def test_add_host(self):
        """Add a host."""
        layout = cping.layouts.Layout(cping.protocols.Ping())
        self.assertIn(layout.add_host('localhost'), layout.hosts)

    def test_add_host_invalid_type_address(self):
        """Add a host with an invalid address type."""
        layout = cping.layouts.Layout(cping.protocols.Ping())

        with self.assertRaisesRegex(TypeError, 'address must be a string'):
            layout.add_host(None)

    def test_remove_host(self):
        """Add a host."""
        layout = cping.layouts.Layout(cping.protocols.Ping())
        host = layout.add_host('localhost')

        self.assertIn(host, layout.hosts)

        layout.remove_host(host)
        self.assertNotIn(host, layout.hosts)

    def test_remove_host_invalid_value_host(self):
        """Attempt to remove a non-existent host."""
        ping = cping.protocols.Ping()
        layout = cping.layouts.Layout(ping)
        host = ping('127.0.0.1')

        with self.assertRaisesRegex(ValueError, 'x not in list'):
            layout.remove_host(host)

    def test_invalid_type_protocol(self):
        """Create an instance of Layout with an invalid protocol type."""
        regex = 'protocol must be an instance of cping.protocols.Ping'

        with self.assertRaisesRegex(TypeError, regex):
            cping.layouts.Layout(None)

    def test_read_only_hosts(self):
        """Layout's hosts attribute is read only."""
        layout = cping.layouts.Layout(cping.protocols.Ping())

        # Confirm a copy is returned
        self.assertIsNot(layout.hosts, layout.hosts)

        with self.assertRaisesRegex(AttributeError, 'can.t set attribute'):
            layout.hosts = None

    def test_read_only_protocol(self):
        """Layout's protocol attribute is read only."""
        ping = cping.protocols.Ping()
        layout = cping.layouts.Layout(ping)
        self.assertIs(layout.protocol, ping)

        with self.assertRaisesRegex(AttributeError, 'can.t set attribute'):
            layout.protocol = None

    def test___call__(self):
        """Ensure __call__ raises NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            cping.layouts.Layout(cping.protocols.Ping())()
