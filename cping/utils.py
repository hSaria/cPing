"""Utility code (stub module)"""
import threading


def create_shared_event(*events):
    """Returns an instance of `threading.Event` which will become set when any of
    the `events` are set (cleared when all are cleared).

    Args:
        *events (threading.Event): the events to monitor
    """
    shared_event = threading.Event()

    # Set shared_event if any of the events are set; cleared otherwise.
    def update():
        if any((event.is_set() for event in events)):
            shared_event.set()
        else:
            shared_event.clear()

    # Patch the event's set and clear methods to also update the shared event
    def patch_event(event):
        # pylint: disable=protected-access
        event._clear = event.clear
        event._set = event.set

        patched_clear = lambda: (event._clear(), update())
        patched_set = lambda: (event._set(), update())

        return patched_clear, patched_set

    for event in events:
        event.clear, event.set = patch_event(event)

    return shared_event


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
