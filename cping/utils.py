"""Utility code (stub module)"""


def stagger_start(hosts, interval):
    """Start the hosts over the duration of an interval. For instance, three
    hosts are staggered over an interval like so:
    interval: |-------||-------||-------|
    first:    |---1--->|---1--->|---1--->
    second:      |---2--->|---2--->|---2--->
    third:          |---3--->|---3--->|---3--->

    Args:
        hosts (list): The list of hosts to start.
        interval (float): The duration over which the hosts are started.
    """
    stagger_interval = interval / len(hosts)

    for index, host in enumerate(hosts):
        host.start(delay=stagger_interval * index)
