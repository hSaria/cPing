'''Utility code (stub module)'''
import math
import re
import threading

DATA_LENGTH = 24
SPARKLINE_STABLE_STDEV = 5


def create_shared_event(*events):
    '''Returns an instance of `threading.Event` which will become set when any of
    the `events` are set (cleared when all are cleared).

    Args:
        *events (threading.Event): the events to monitor
    '''
    shared_event = threading.Event()

    # Set shared_event if any of the events are set; cleared otherwise.
    def update():
        if any((event.is_set() for event in events)):
            shared_event.set()
        else:
            shared_event.clear()

    # Patch the event's set and clear methods to also update the shared event
    def patch_event(event):
        # Keep references to the event's original functions
        original_clear = event.clear
        original_set = event.set

        patched_clear = lambda: (original_clear(), update())
        patched_set = lambda: (original_set(), update())

        return patched_clear, patched_set

    for event in events:
        event.clear, event.set = patch_event(event)

    return shared_event


def generate_data(length=DATA_LENGTH, data=b':github.com/hSaria/cPing'):
    '''Returns string which repeats `data` until it reaches `length`.'''
    return (data * (length // len(data) + 1))[:length]


def natural_ordering_sort_key(string, _regex=re.compile(r'(\d+)')):
    '''Returns a list containing the `string`, but with the numbers converted
    into integers. Meant to be used as a natural-sorting key.'''
    return [int(x) if x.isdigit() else x for x in _regex.split(string.lower())]


def sparkline_point(value, minimum, maximum, stdev=None):
    '''Returns one of `▁▂▃▄▅▆▇` to be used as part of a sparkline. If `stdev` is
    less than SPARKLINE_STABLE_STDEV, `▁▂` are not used as that might indicate
    an unstable host.

    Args:
        value (float): the value to normalize
        minimum (float): the minimum value in the data set
        maximum (float): the maximum value in the data set
        stdev (float): the standard deviation of the data set
    '''
    if maximum == minimum:
        # Avoid divide-by-zero when there's only one data point
        normalized_value = 0
    else:
        # The value between 0 and 1 relative to the minimum and maximum
        normalized_value = (value - minimum) / (maximum - minimum)

    # The range of value falls under the stable delta range
    if isinstance(stdev, float) and stdev < SPARKLINE_STABLE_STDEV:
        # Distribute between 0.2 and 1.0 to avoid sporadic sparklines
        normalized_value = ((1.0 - 0.2) * normalized_value) + 0.2

    # Scale the value logarithmicly between 0 and 1
    scaled_value = math.log(max((normalized_value * 10), 1), 10)

    # Unicode blocks (they're in hex): https://w.wiki/zKh
    return chr(0x2581 + round(scaled_value * 6))


def stagger_start(hosts, interval):
    '''Start the hosts over the duration of an interval. For instance, three
    hosts are staggered over an interval like so:
    interval: |-------||-------||-------|
    first:    |---1--->|---1--->|---1--->
    second:      |---2--->|---2--->|---2--->
    third:          |---3--->|---3--->|---3--->

    Args:
        hosts (list): The list of hosts to start.
        interval (float): The duration over which the hosts are started.
    '''
    stagger_interval = interval / len(hosts)

    for index, host in enumerate(hosts):
        host.start(delay=stagger_interval * index)
