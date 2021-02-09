"""ICMP echo ping."""
import array
import random
import select
import socket
import struct
import sys
import threading
import time

import cping.protocols

DATA_LENGTH = 24


class Ping(cping.protocols.Ping):
    """ICMP echo ping. The possible results:
        * latency=x, error=False: ICMP echo reply
        * latency=-1, error=False: timeout
    """
    def ping_loop(self, host):
        try:
            host_info = socket.getaddrinfo(host=host.address, port=None)[0]
        except socket.gaierror:
            host.status = 'Host resolution failed'
            return

        session = Session(host_info)

        while True:
            latency = session.probe(self.interval)
            host.add_result(latency)

            # Account for the duration of the previous test
            timeout = self.interval - latency if latency != -1 else 0

            # Sleep until signaled to stop or the timeout expires
            if host.stop_signal.wait(timeout):
                break


class Session():
    """A ping session to a host."""
    match_queue = []
    sequence = -1
    sequence_lock = threading.Lock()

    icmpv4_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_RAW if sys.platform == 'win32' else socket.SOCK_DGRAM,
        socket.IPPROTO_ICMP,
    )
    icmpv6_socket = socket.socket(
        socket.AF_INET6,
        socket.SOCK_RAW if sys.platform == 'win32' else socket.SOCK_DGRAM,
        socket.IPPROTO_ICMPV6,
    )

    def __init__(self, host_info):
        """Constructor.

        Args:
            host_info (tuple): an item from the `socket.getaddrinfo` list.
        """
        self.host_info = host_info
        self.identifier = random.randrange(1, 2**16)

    def create_icmp_echo(self):
        """Returns tuple of an ICMP echo request and its expected reply (bytes)."""
        identifier = self.identifier & 0xffff
        sequence = self.next_sequence() & 0xffff
        data = generate_data(DATA_LENGTH)

        # ICMP type field differs between ICMPv4 and ICMPv6
        if self.host_info[0] == socket.AF_INET:
            request_type, reply_type = 8, 0
        else:
            request_type, reply_type = 128, 129

        request = struct.pack('!BBHHH', request_type, 0, 0, identifier,
                              sequence) + data
        request = request[:2] + get_checksum(request) + request[4:]

        # Identifier ignored; see matching logic in `Session.receiver`
        reply = struct.pack('!BBHHH', reply_type, 0, 0, 0, sequence) + data

        return request, reply

    @staticmethod
    def next_sequence():
        """Returns the next sequence, incrementing it by 1."""
        with Session.sequence_lock:
            Session.sequence += 1

        return Session.sequence

    def probe(self, wait):
        """Returns the latency to `self.host_info` in seconds. If the host does
        not respond, `-1` is returned.

        Args:
            wait (float): The interval to wait before declaring the host down.
        """
        request, reply = self.create_icmp_echo()
        receive_event = threading.Event()

        # Add to the expected packet to the receiver queue
        self.match_queue.append((reply, receive_event))

        if self.host_info[0] == socket.AF_INET:
            self.icmpv4_socket.sendto(request, self.host_info[4])
        else:
            self.icmpv6_socket.sendto(request, self.host_info[4])

        checkpoint = time.time()
        latency = time.time() - checkpoint if receive_event.wait(wait) else -1

        # Remove from the queue
        self.match_queue.remove((reply, receive_event))

        # Increment the sequence for the next ping
        self.sequence += 1

        return latency

    @staticmethod
    def receiver():
        """Monitors the ICMPv4 and ICMPv6 sockets for packets and attempt to
        match them against `Session.match_queue`."""
        icmp_sockets = [Session.icmpv4_socket, Session.icmpv6_socket]

        while True:
            # Block until there is data to be read
            for protocol_socket in select.select(icmp_sockets, [], [])[0]:
                data = protocol_socket.recv(2048)

                # Ignore checksum (IPv6 requires a pseudo-header that's too much
                # work to calculate and is already calculated by the kernel) and
                # identifier (Linux overwrites identifier, so a globally-unique
                # sequence is used instead). Also, the IPv4 header is included
                # in the data on macOS, so we have to extract the ICMP message.
                data = b''.join([
                    data[-(DATA_LENGTH + 8):-(DATA_LENGTH + 6)],
                    (b'\x00' * 4),
                    data[-(DATA_LENGTH + 2):],
                ])

                for expected, event in Session.match_queue.copy():
                    if data == expected:
                        event.set()
                        break


def get_checksum(data):
    """Returns checksum of `data`. Not meant for ICMPv6 as that requires an IPv6
    pseudo-header. ICMP checksum: www.ietf.org/rfc/rfc1071.html#section-4.1."""
    # 0-pad data of odd length
    if len(data) % 2 == 1:
        data += b'\x00'

    # The sum of the data, split into 16-bit words
    checksum = sum(array.array('H', data))

    # End-around carry the sum to 16 bits
    while checksum >> 16:
        checksum = (checksum & 0xffff) + (checksum >> 16)

    # One's complement of the sum, normalized to 16 bits
    return struct.pack('!H', socket.htons(~checksum & 0xffff))


def generate_data(length, data=b':github.com/hsaria/cping'):
    """Returns string which repeats `data` until it reaches `length`."""
    return (data * (length // len(data) + 1))[:length]


# Begin listening on the ICMP socekts. Daemonized to exit when cping exits
threading.Thread(target=Session.receiver, daemon=True).start()
