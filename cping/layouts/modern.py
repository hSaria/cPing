'''Curses-based interactive window.'''
import curses
import math
import sys

import cping.layouts
import cping.protocols
import cping.utils

COLUMN_DELIMITER = '  '
COLUMN_WIDTH_MINIMUM = 6


class Layout(cping.layouts.Layout):
    '''Curses-based interactive window.'''
    colors = {}

    def __call__(self):
        # Perform curses initialization code and call render, then clean up
        curses.wrapper(self.render)

    @staticmethod
    def initialize_colors():
        '''Populate the `Layout.colors` dictionaries with the attribute numbers.'''
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        Layout.colors['green'] = curses.color_pair(1)
        curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
        Layout.colors['red'] = curses.color_pair(2)
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        Layout.colors['yellow'] = curses.color_pair(3)

    @staticmethod
    def render_sparkline(window, line, column, host, length):
        '''Render a sparkline at the requested position.

        Args:
            window (curses.window): Window to which the sparkline is rendered.
            line (int): y coordinate.
            column (int): x coordinate of the start of the sparkline.
            host (cping.protocols.Host): Source of the sparkline's data.
            length (int): The maximum length of the sparkline.
        '''
        for result in list(host.results)[-length:]:
            if result['latency'] == -1:
                color = 'red'
                point = '.' if sys.platform == 'win32' else '░'
            else:
                color = 'yellow' if result['error'] else 'green'
                point = '!'

                if sys.platform != 'win32':
                    point = cping.utils.sparkline_point(
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
        '''Calls `window.addnstr` to render the table based on the selection.

        Args:
            window (curses.window): Window to which the table is rendered.
            table (list): The results table (i.e. `get_table`).
            selection (int): The index of the selected row.
        '''
        lines, columns = window.getmaxyx()

        page = get_table_page(table, lines - 1, selection)
        page_count = math.ceil(len(table) / (lines - 1))
        page_number = (selection // (lines - 1)) + 1

        footer = get_table_footer(page_count, page_number, selection)
        footer = footer.ljust(columns)

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
        '''Start rendering the layout. Blocking function meant to be called with
        `curses.wrapper(self.render)`.'''
        # pylint: disable=too-many-branches
        Layout.initialize_colors()

        # Set the timeout (ms) for `windows.getch`
        window.timeout(int(self.protocol.interval * 1000))

        # State tracking
        button = selection = sort_key = 0

        while button != ord('q'):
            table = get_table(self.hosts, sort_key)
            Layout.render_table(window, table, selection)

            # Clear burst mode to avoid sticking while waiting on getch
            for host in self.hosts:
                host.burst_mode.clear()

            button = window.getch()

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
                        table[selection]['host'].stop(block=True)
                    else:
                        table[selection]['host'].start()
                elif any((host.is_running() for host in self.hosts)):
                    for host in self.hosts:
                        host.stop(block=True)
                else:
                    interval = self.protocol.interval
                    cping.utils.stagger_start(self.hosts, interval)
            elif button in range(48, 48 + 7):
                # Sorting: 48 is the '0' key, so this is effectively `range(7)`
                sort_key = get_table_sort_key(button % 48, sort_key)

            # Flush input buffer to remove queued keys pressed during processing
            curses.flushinp()


def get_host_columns(host):
    '''Returns a list of strings containing host, min, avg, max, stdev, loss.

    Args:
        host (cping.protocols.Host): Host from which to get the details.
    '''
    columns = [str(host)]

    for stat in ['min', 'avg', 'max', 'stdev', 'loss']:
        if host.results_summary[stat] is None:
            columns.append('-  ')
            continue

        if stat == 'loss':
            columns.append(f'{host.results_summary[stat]:.0%} ')
        else:
            columns.append(f'{host.results_summary[stat]:.2f}')

    return columns


def get_table(hosts, sort_key=0):
    '''Returns a list of dictionaries, one for each row.

    Args:
        hosts (list): The hosts upon which the table is based.
        sort_key (int): Passed to `sort_hosts`.
    '''
    # Table starts with the header
    header = [' HOST ', 'MIN ', 'AVG ', 'MAX ', 'STD ', 'LOSS ']
    table = [{'columns': header, 'attrs': curses.A_STANDOUT}]

    # Add sorting indicator
    if isinstance(sort_key, int) and 0 < abs(sort_key) <= len(header):
        header[abs(sort_key) - 1] += '▲' if sort_key > 0 else '▼'

    # Add the hosts, their columns, and the appropriate curses attributes
    for host in sort_hosts(hosts, sort_key):
        row = {
            'host': host,
            'columns': get_host_columns(host),
            'attrs': curses.A_NORMAL,
        }

        if not host.is_running():
            row['attrs'] = curses.A_UNDERLINE

        table.append(row)

    # Calculate the maximum width of each column among all rows
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
    '''Returns a footer (string) for a table.

    Args:
        page_count (int): The total number of pages.
        page_number (int): Currently selected page.
    '''
    footer = f' Page {page_number}/{page_count} | '

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
    '''Returns a subset of the table based on the selection.

    Args:
        table (list): The list of rows to filter.
        size (int): Number of rows to return in the page.
        selection (int): The index of the item to be highlighted.
    '''
    page = []

    for index, row in enumerate(table):
        # Row in the selected page
        if index // size == selection // size:
            page.append(row)

    return page


def get_table_sort_key(new, current):
    '''Returns the new sorting index depending on the current one. Positive
    implies ascending, negative is descending, and `0` means no sorting. The
    sorting will cycle between ascending, descending, and `0` if `new` is the
    same as `abs(current)`.

    Args:
        new (int): the sorting key being requested.
        current (int): the sorting key currently being used.
    '''
    if isinstance(current, int) and abs(current) == new:
        if current < 0:
            # Currently descending; reset sorting
            return 0
        # Currently ascending; change to descending
        return -current
    # Currently None or some other key; change to ascending
    return new


def host_results_sort_key(host, key):
    '''Returns `host.results_summary.get(key)` if it's not None. Otherise 10**6.'''
    value = host.results_summary.get(key)
    return value if value is not None else 10**6


def sort_hosts(hosts, sort_key=0):
    '''Returns `hosts`, sorted according to `sort_key`.

    Args:
        hosts (list): The list of hosts to be sorted.
        sort_key (int): The column by which the table is sorted. Starting
            at 1, the column numbers map to: host, min, avg, max, stdev, and
            loss.
    '''
    sort_keys = {
        1: lambda host: cping.utils.natural_ordering_sort_key(str(host)),
        2: lambda host: host_results_sort_key(host, 'min'),
        3: lambda host: host_results_sort_key(host, 'avg'),
        4: lambda host: host_results_sort_key(host, 'max'),
        5: lambda host: host_results_sort_key(host, 'stdev'),
        6: lambda host: host_results_sort_key(host, 'loss'),
    }

    # Get the respective lambda sort key, defaulting to no sorting
    key = sort_keys.get(abs(sort_key or 0), lambda host: 0)
    reverse = isinstance(sort_key, int) and sort_key < 0

    return sorted(hosts, key=key, reverse=reverse)
