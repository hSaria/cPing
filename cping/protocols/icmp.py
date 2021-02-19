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
SOCKET_TYPE = socket.SOCK_RAW if sys.platform == 'win32' else socket.SOCK_DGRAM


class Ping(cping.protocols.Ping):
    """ICMP echo ping. The possible results:
        * latency=x, error=False: ICMP echo reply
        * latency=-1, error=False: timeout
    """
    icmpv4_socket = icmpv6_socket = None
    match_queue = []

    def __init__(self, *args, **kwargs):
        # Create the ICMP sockets if they haven't been already
        if Ping.icmpv4_socket is None:
            Ping.icmpv4_socket = socket.socket(socket.AF_INET, SOCKET_TYPE,
                                               socket.IPPROTO_ICMP)
            Ping.icmpv6_socket = socket.socket(socket.AF_INET6, SOCKET_TYPE,
                                               socket.IPPROTO_ICMPV6)

            # Begin listening on the ICMP sockets. Daemonized to exit with cping
            threading.Thread(target=Ping.receiver, daemon=True).start()

        super().__init__(*args, **kwargs)

    @staticmethod
    def receiver():
        """Monitors the ICMPv4 and ICMPv6 sockets for packets and attempt to
        match them against `Ping.match_queue`."""
        icmp_sockets = [Ping.icmpv4_socket, Ping.icmpv6_socket]

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

                for expected, event in Ping.match_queue.copy():
                    if data == expected:
                        event.set()
                        break

    def ping_loop(self, host):
        try:
            host_info = socket.getaddrinfo(host=host.address, port=None)[0]
        except socket.gaierror:
            host.status = 'Host resolution failed'
            return

        session = Session(4 if host_info[0] == socket.AF_INET else 6)

        while True:
            request, reply = session.create_icmp_echo()
            receive_event = threading.Event()
            latency = -1

            # Add the expected packet to the receiver queue
            Ping.match_queue.append((reply, receive_event))

            checkpoint = time.perf_counter()

            try:
                if host_info[0] == socket.AF_INET:
                    Ping.icmpv4_socket.sendto(request, host_info[4])
                else:
                    Ping.icmpv6_socket.sendto(request, host_info[4])

                if receive_event.wait(self.interval):
                    latency = time.perf_counter() - checkpoint
            except OSError as exception:
                host.status = str(exception)
                break
            finally:
                # Remove from the queue
                Ping.match_queue.remove((reply, receive_event))

            host.add_result(latency)

            # Sleep until signaled to stop or the timeout expires
            if host.stop_signal.wait(self.get_timeout(latency, host)):
                break


class Session():
    """A ping session to a host."""
    sequence = -1
    sequence_lock = threading.Lock()

    def __init__(self, family):
        """Constructor.

        Args:
            family (int): The IP family of the host. IPv4 if `4`, else IPv6.
        """
        self.family = 4 if family == 4 else 6
        self.identifier = random.randrange(1, 2**16)

    @staticmethod
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

    @staticmethod
    def generate_data(length, data=b':github.com/hSaria/cPing'):
        """Returns string which repeats `data` until it reaches `length`."""
        return (data * (length // len(data) + 1))[:length]

    @staticmethod
    def next_sequence():
        """Returns the next sequence, incrementing it by 1."""
        with Session.sequence_lock:
            Session.sequence += 1
            return Session.sequence

    def create_icmp_echo(self):
        """Returns tuple of an ICMP echo request and its expected reply (bytes)."""
        identifier = self.identifier & 0xffff
        sequence = Session.next_sequence() & 0xffff
        data = Session.generate_data(DATA_LENGTH)

        # ICMP type field differs between ICMPv4 and ICMPv6
        request_type, reply_type = (8, 0) if self.family == 4 else (128, 129)

        # Checksum is calculated with the checksum in the header set to 0
        request = struct.pack('!BBHHH', request_type, 0, 0, identifier,
                              sequence) + data
        request = request[:2] + Session.get_checksum(request) + request[4:]

        # Identifier ignored; see matching logic in `Ping.receiver`
        reply = struct.pack('!BBHHH', reply_type, 0, 0, 0, sequence) + data

        return request, reply
