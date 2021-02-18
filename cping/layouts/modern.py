"""Curses-based interactive window."""
import curses
import math
import re
import sys

import cping.layouts
import cping.protocols

COLUMN_DELIMITER = '  '
COLUMN_WIDTH_MINIMUM = 6
SPARKLINE_STABLE_STDEV = 5


class Layout(cping.layouts.Layout):
    """Curses-based interactive window."""
    colors = {}

    def __call__(self):
        # Perform curses initialization code and call render, then clean up
        curses.wrapper(self.render)

    @staticmethod
    def initialize_colors():
        """Populate the `Layout.colors` dictionaries with the attribute numbers."""
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        Layout.colors['green'] = curses.color_pair(1)
        curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
        Layout.colors['red'] = curses.color_pair(2)
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        Layout.colors['yellow'] = curses.color_pair(3)

    @staticmethod
    def render_sparkline(window, line, column, host, length):
        """Render a sparkline at the requested position.

        Args:
            window (curses.window): Window to which the sparkline is rendered.
            line (int): y coordinate.
            column (int): x coordinate of the start of the sparkline.
            host (cping.protocols.Host): Source of the sparkline's data.
            length (int): The maximum length of the sparkline.
        """
        for result in list(host.results)[-length:]:
            if result['latency'] == -1:
                color = 'red'
                point = '.' if sys.platform == 'win32' else '░'
            else:
                color = 'yellow' if result['error'] else 'green'
                point = '!'

                if sys.platform != 'win32':
                    point = sparkline_point(
                        result['latency'] * 1000,
                        host.results_summary['min'],
                        host.results_summary['max'],
                        host.results_summary['stdev'],
                    )

            color = Layout.colors.get(color, curses.A_NORMAL)
            window.addstr(line, column, point, color)

            # Shift to next point
            column += 1

    @staticmethod
    def render_table(window, table, selection):
        """Calls `window.addnstr` to render the table based on the selection.

        Args:
            window (curses.window): Window to which the table is rendered.
            table (list): The results table (i.e. `get_table`).
            selection (int): The index of the selected row.
        """
        lines, columns = window.getmaxyx()

        page = get_table_page(table, lines - 1, selection)
        page_count = math.ceil(len(table) / (lines - 1))
        page_number = (selection // (lines - 1)) + 1

        footer = get_table_footer(page_count, page_number,
                                  selection).ljust(columns)

        try:
            window.erase()

            # Add the page to the window
            for index, row in enumerate(page):
                # Extend the header to the end of the screen
                if page_number == 1 and index == 0:
                    row['line'] = row['line'].ljust(columns)

                # Highlight selection; account for pagination
                if index == selection % (lines - 1):
                    row['attrs'] |= curses.A_BOLD

                window.addnstr(index, 0, row['line'], columns, row['attrs'])

                # Add the sparkline if this isn't the header
                if row.get('host'):
                    sparkline_length = columns - len(row['line'])

                    if sparkline_length > 0:
                        row['host'].set_results_length(sparkline_length)
                        Layout.render_sparkline(
                            window,
                            index,
                            len(row['line']),
                            row['host'],
                            sparkline_length,
                        )

            # Add a footer to the bottom of the screen
            window.addnstr(lines - 1, 0, footer, columns, curses.A_STANDOUT)
            window.refresh()
        except curses.error:
            # Triggers when excessively resizing the window
            pass

    def render(self, window):
        """Start rendering the layout. Blocking function meant to be called with
        `curses.wrapper(self.render)`."""
        # pylint: disable=too-many-branches
        Layout.initialize_colors()

        # Set the timeout (ms) for `windows.getch`
        window.timeout(int(self.protocol.interval * 1000))

        # State tracking
        button = selection = sort_key = 0

        while button != ord('q'):
            table = get_table(self.hosts, sort_key)
            Layout.render_table(window, table, selection)

            button = window.getch()

            # Flush input buffer to remove queued keys pressed during processing
            curses.flushinp()

            if button == curses.KEY_UP:
                selection = max(selection - 1, 0)
            elif button == curses.KEY_DOWN:
                selection = min(selection + 1, len(self.hosts))
            elif button == ord('b'):
                # Burst mode
                if selection > 0:
                    table[selection]['host'].burst_mode.set()
                else:
                    for host in self.hosts:
                        host.burst_mode.set()
            elif button == ord('s'):
                # Start or stop the selected host (all if header selected)
                if selection > 0:
                    if table[selection]['host'].is_running():
                        table[selection]['host'].stop()
                    else:
                        table[selection]['host'].start()
                elif any((host.is_running() for host in self.hosts)):
                    for host in self.hosts:
                        host.stop()
                else:
                    interval = self.protocol.interval
                    cping.protocols.stagger_start(self.hosts, interval)
            elif button in range(48, 48 + 7):
                # Sorting: 48 is the '0' key, so this is effectively `range(7)`
                sort_key = get_table_sort_key(button % 48, sort_key)
            else:
                # Clear burst mode
                for host in self.hosts:
                    host.burst_mode.clear()


def get_host_columns(host):
    """Returns a list of strings containing host, min, avg, max, stdev, loss.

    Args:
        host (cping.protocols.Host): Host from which to get the details.
    """
    columns = [str(host)]

    for stat in ['min', 'avg', 'max', 'stdev', 'loss']:
        if host.results_summary[stat] is not None:
            if stat == 'loss':
                columns.append('{:.0%} '.format(host.results_summary[stat]))
            else:
                columns.append('{:.2f}'.format(host.results_summary[stat]))
        else:
            columns.append('-  ')

    return columns


def get_table(hosts, sort_key=0):
    """Returns a list of dictionaries, one for each row.

    Args:
        hosts (list): The hosts upon which the table is based.
        sort_key (int): Passed to `sort_hosts`.
    """
    # Table starts with the header
    table = [{
        'columns': [' HOST', 'MIN ', 'AVG ', 'MAX ', 'STDEV', 'LOSS'],
        'attrs': curses.A_STANDOUT
    }]

    # Add the hosts, their columns, and the appropriate curses attributes
    for host in sort_hosts(hosts, sort_key):
        if host.is_running():
            attributes = curses.A_NORMAL
        else:
            attributes = curses.A_UNDERLINE

        table.append({
            'host': host,
            'columns': get_host_columns(host),
            'attrs': attributes,
        })

    # Calculate the the maximum width of each column among all rows
    column_widths = [COLUMN_WIDTH_MINIMUM] * 6

    for column in range(6):
        for row in table:
            column_width = len(row['columns'][column])
            column_widths[column] = max(column_width, column_widths[column])

    # Align columns and store the resulting string into the `line` key
    for row in table:
        if row.get('host') and row['host'].status:
            # The header will always be in the table at this point
            padding = len(table[0]['line'])
            status = row['host'].status

            row['line'] = COLUMN_DELIMITER.join([row['columns'][0], status])
            row['line'] = row['line'].ljust(padding)[:padding]
            continue

        for column in range(6):
            # The Host column is left justified
            if column == 0:
                value = row['columns'][column].ljust(column_widths[column])
            else:
                value = row['columns'][column].rjust(column_widths[column])

            row['columns'][column] = value

        row['line'] = COLUMN_DELIMITER.join(row['columns'])

    return table


def get_table_footer(page_count, page_number, selection):
    """Returns a footer (string) for a table.

    Args:
        page_count (int): The total number of pages.
        page_number (int): Currently selected page.
    """
    footer = ' Page {}/{} | '.format(page_number, page_count)

    if selection == 0:
        footer += '(All): '

    # Host actions
    footer += '[B]urst mode (hold), '
    footer += '[S]tart/[S]top | '

    # Layout actions
    footer += '[▲/▼] Change selection, '
    footer += '[1-6] Order table, '
    footer += '[Q]uit'

    return footer.upper()


def get_table_page(table, size, selection):
    """Returns a subset of the table based on the selection.

    Args:
        table (list): The list of rows to filter.
        size (int): Number of rows to return in the page.
        selection (int): The index of the item to be highlighted.
    """
    page = []

    for index, row in enumerate(table):
        # Row in the selected page
        if index // size == selection // size:
            page.append(row)

    return page


def get_table_sort_key(new, current):
    """Returns the new sorting index depending on the current one. Positive
    implies ascending, negative is descending, and `0` means no sorting. The
    sorting will cycle between ascending, descending, and `0` if `new` is the
    same as `abs(current)`.

    Args:
        new (int): the sorting key being requested.
        current (int): the sorting key currently being used.
    """
    if isinstance(current, int) and abs(current) == new:
        if current < 0:
            # Currently descending; reset sorting
            return None
        # Currently ascending; change to descending
        return -current
    # Currently None or some other key; change to ascending
    return new


def host_results_sort_key(host, key):
    """Returns `host.results_summary.get(key)` if it's not None. Otherise 10**6."""
    value = host.results_summary.get(key)
    return value if value is not None else 10**6


def natural_ordering_sort_key(string, _regex=re.compile(r'(\d+)')):
    """Returns a list containing the `string`, but with the numbers converted
    into integers. Meant to be used as a natural-sorting key."""
    return [int(x) if x.isdigit() else x.lower() for x in _regex.split(string)]


def sort_hosts(hosts, sort_key=0):
    """Returns `hosts`, sorted according to `sort_key`.

    Args:
        hosts (list): The list of hosts to be sorted.
        sort_key (int): The column by which the table is sorted. Starting
            at 1, the column numbers map to: host, min, avg, max, stdev, and
            loss.
    """
    key = lambda host: 0
    reverse = False

    if isinstance(sort_key, int) and sort_key != 0:
        reverse = sort_key < 0

        if abs(sort_key) == 1:
            key = lambda host: natural_ordering_sort_key(str(host))
        elif abs(sort_key) == 2:
            key = lambda host: host_results_sort_key(host, 'min')
        elif abs(sort_key) == 3:
            key = lambda host: host_results_sort_key(host, 'avg')
        elif abs(sort_key) == 4:
            key = lambda host: host_results_sort_key(host, 'max')
        elif abs(sort_key) == 5:
            key = lambda host: host_results_sort_key(host, 'stdev')
        elif abs(sort_key) == 6:
            key = lambda host: host_results_sort_key(host, 'loss')

    return sorted(hosts, key=key, reverse=reverse)


def sparkline_point(value, minimum, maximum, stdev=None):
    """Returns one of `▁▂▃▄▅▆▇` to be used as part of a sparkline. If `stdev` is
    less than SPARKLINE_STABLE_STDEV, `▁▂` are not used as it could incorrectly
    indicate an unstable host.

    Args:
        value (float): the value to normalize
        minimum (float): the minimum value in the data set
        maximum (float): the maximum value in the data set
        stdev (float): the standard deviation of the data set
    """
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
