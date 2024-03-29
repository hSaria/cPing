'''Concurrect ping to multiple hosts with support for ICMP and TCP.'''
from cping.layouts.legacy import Layout as LayoutLegacy
from cping.layouts.modern import Layout as LayoutModern
from cping.protocols import Host
from cping.protocols.icmp import Ping as PingICMP
from cping.protocols.tcp import Ping as PingTCP

__version__ = '0.1.12-dev'
