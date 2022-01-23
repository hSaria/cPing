'''A line-based, non-interactive layout. The "original".'''
import shutil
import time

import cping.layouts

HISTOGRAM_LENGTH_MINIMUM = 5


class Layout(cping.layouts.Layout):
    '''A line-based, non-interactive layout. The "original".'''

    def __call__(self):
        try:
            # Enable alternate screen buffer
            print('\x1b[?1049h', end='')

            while any((host.is_running() for host in self.hosts)):
                # Move to top left, then print table
                print(f'\x1b[H{get_table(self.hosts)}', end='', flush=True)
                time.sleep(self.protocol.interval)
        finally:
            # Disable alternate screen buffer
            print('\x1b[?1049l', end='')

            # Print the last summary, including any overflowing hosts
            print(get_table(self.hosts, all_hosts=True), end='')


def format_host(host, host_padding, line_width):
    '''Returns a line representing a summary of the host's results.'''
    # line_width - host - min (8) - avg (8) - max (8) - stdev (8) - loss (8)
    host.set_results_length(line_width - host_padding - 8 * 5)
    line = str(host).ljust(host_padding)

    if host.status:
        return line + '   ' + host.status

    for stat in ['min', 'avg', 'max', 'stdev']:
        if host.results_summary[stat] is not None:
            line += f' {host.results_summary[stat]:>7.2f}'
        else:
            line += '     -  '

    if host.results_summary['loss'] is not None:
        line += f' {host.results_summary["loss"]:>5.0%}  '
    else:
        line += '    -   '

    return line + get_histogram(host, line_width - len(line))


def get_color(color, last_color=None):
    '''Returns the ANSI code for `color`, taking in mind `last_color` to skip
    unnecessary color codes. `color` can be green, red, yellow, and reset'''
    if color != last_color:
        return {
            'green': '\x1b[32m',
            'red': '\x1b[31m',
            'yellow': '\x1b[33m',
            'reset': '\x1b[39m',
        }.get(color, '')

    return ''


def get_histogram(host, length):
    '''Returns an ANSI-colored string representing the host's results.'''
    # Output optimization by only including color markers when the color changes
    line = ''
    length = max(length, HISTOGRAM_LENGTH_MINIMUM)
    last_color = None

    for result in list(host.results)[-length:]:
        if result['latency'] == -1:
            line += get_color('red', last_color) + '.'
            last_color = 'red'
        else:
            color = 'green' if not result['error'] else 'yellow'
            line += get_color(color, last_color) + '!'
            last_color = color

    # Include a color reset at the end of the line
    return line + get_color('reset')


def get_table(hosts, all_hosts=False):
    '''Returns a table (string) of the hosts' results.

    Args:
        hosts (list): A list... of hosts... Yeah.
        all_hosts (bool): If `False`, table won't exceed screen's height.
    '''
    table = ''
    term_size = shutil.get_terminal_size()
    host_padding = max([len(str(x)) for x in hosts]) + 1

    for index, host in enumerate(hosts):
        # Not printing all hosts and lines limit reached
        if not all_hosts and index >= term_size.lines - 1:
            break

        host_line = format_host(host, host_padding, term_size.columns)

        # Clear to end of line
        table += host_line + '\x1b[K\n'

    # Clear to end of screen
    table += '\x1b[J'

    # Not printing all hosts and some hosts overflowed
    if not all_hosts and len(hosts) > term_size.lines - 1:
        table += f'+{len(hosts) - (term_size.lines - 1)} more'

    return table
