'''ICMP echo ping.'''
import array
import random
import select
import socket
import struct
import sys
import threading
import time

import cping.protocols

SOCKET_TYPE = socket.SOCK_RAW if sys.platform == 'win32' else socket.SOCK_DGRAM


class Ping(cping.protocols.Ping):
    '''ICMP echo ping. The possible results:
        * latency=x, error=False: ICMP echo reply
        * latency=x, error=True: late reply
        * latency=-1, error=False: timeout
    '''
    icmpv4_socket = icmpv6_socket = None
    host_map = {}

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
        '''Handles incoming ICMPv4 and ICMPv6 sockets for packets by signalling
        the respective host's ping loop or updating late replies.'''
        icmp_sockets = [Ping.icmpv4_socket, Ping.icmpv6_socket]

        while True:
            # Block until there is at least one socket ready to be read
            protocol_socket = select.select(icmp_sockets, [], [])[0][0]

            # Strip the ICMP reply as macOS includes the IPv4 header in data
            # pylint: disable=invalid-unary-operand-type  # linter bug
            data = protocol_socket.recv(8192)[-Session.packet_struct.size:]

            # Malformed packet
            if len(data) < Session.packet_struct.size:
                continue

            packet = Session.packet_struct.unpack(data)
            sequence, identifier, timestamp = packet[-3:]

            # Unknown packet
            if identifier not in Ping.host_map:
                continue

            latency = time.perf_counter() - timestamp
            host, event, interval = Ping.host_map[identifier]

            # Search through all of the results, including the hidden ones.
            for result in host.raw_results:
                if result['info'] == sequence:
                    result['latency'] = latency

                    # Reply arrived on time; inform the host's ping loop to continue
                    if latency <= interval:
                        event.set()
                    # Late reply; the ping loop is already in the next iteration
                    else:
                        result['error'] = True

                    break

    def ping_loop(self, host):
        try:
            host_info = socket.getaddrinfo(host=host.address, port=None)[0]
        except socket.gaierror:
            host.status = 'Host resolution failed'
            return

        session = Session(4 if host_info[0] == socket.AF_INET else 6)
        receive_event = threading.Event()

        Ping.host_map[session.identifier] = host, receive_event, self.interval

        while not host.stop_signal.is_set():
            receive_event.clear()
            latency = -1
            request = session.create_icmp_echo()

            # Initially hidden to avoid showing a downed result
            result = host.add_result(latency,
                                     hidden=True,
                                     info=session.sequence)

            try:
                if host_info[0] == socket.AF_INET:
                    Ping.icmpv4_socket.sendto(request, host_info[4])
                else:
                    Ping.icmpv6_socket.sendto(request, host_info[4])

                # A response was received; update the latency for an accurate wait
                if receive_event.wait(self.interval):
                    latency = result['latency']
            except OSError as exception:
                host.status = str(exception)
                break

            result['hidden'] = False

            # Block until signaled to continue
            host.wait(latency)

        Ping.host_map.pop(session.identifier)


class Session:
    '''A ping session to a host.'''
    # The final `Hf` is the data, containing the identifier and the timestamp
    packet_struct = struct.Struct('!BBHHHHf')

    def __init__(self, family):
        '''Constructor.

        Args:
            family (int): The IP family of the host. IPv4 if `4`, else IPv6.
        '''
        # ICMP type field differs between ICMPv4 and ICMPv6
        self.packet_type = 8 if family == 4 else 128
        self.sequence = random.randrange(1, 2**16)

        # Ensure the session identifier is unique between hosts
        while True:
            self.identifier = random.randrange(1, 2**16)

            if self.identifier not in Ping.host_map:
                break

    @staticmethod
    def get_checksum(data):
        '''Returns checksum of `data`. Not meant for ICMPv6 as that requires an IPv6
        pseudo-header. ICMP checksum: www.ietf.org/rfc/rfc1071.html#section-4.1.'''
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

    def create_icmp_echo(self):
        '''Returns the bytes of an ICMP echo request.'''
        self.sequence = self.sequence + 1 & 0xffff

        # The data contains another copy of the identifier as the one in the
        # header is stripped in some Linux distributions
        request = Session.packet_struct.pack(self.packet_type, 0, 0,
                                             self.identifier, self.sequence,
                                             self.identifier,
                                             time.perf_counter())

        # Checksum is calculated with the checksum in the header set to 0
        request = request[:2] + Session.get_checksum(request) + request[4:]

        return request
