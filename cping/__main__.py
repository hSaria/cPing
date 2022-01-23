'''Command line script.'''
import argparse
import sys

import cping
import cping.utils

INTERVAL_MINIMUM = 0.1


def args_init(args=None):
    '''Returns the parsed arguments (an instance of argparse.Namespace).

    Args:
        args (list): A list of program arguments, Defaults to sys.argv.
    '''
    formatter = lambda prog: argparse.HelpFormatter(prog, max_help_position=30)
    parser = argparse.ArgumentParser(formatter_class=formatter)

    parser.add_argument('host', nargs='+', help='one or more hosts to ping')

    parser.add_argument('-i',
                        '--interval',
                        metavar='sec',
                        type=float,
                        default=1,
                        help='ping interval (default: %(default)s)')

    layout_help = 'display format. choices: %(choices)s (default: %(default)s)'

    # Suppress the layout option on Windows as it's currently limited to modern
    if sys.platform == 'win32':
        layout_help = argparse.SUPPRESS

    parser.add_argument('-l',
                        '--layout',
                        metavar='name',
                        type=str.lower,
                        choices=['legacy', 'modern'],
                        default='modern',
                        help=layout_help)

    parser.add_argument('-p',
                        '--port',
                        metavar='port',
                        type=int,
                        help='test using TCP SYN (default: ICMP echo)')

    args = parser.parse_args(args=args)

    if args.interval < INTERVAL_MINIMUM:
        parser.error(f'minimum interval is {INTERVAL_MINIMUM}')

    return args


def main(args=None):
    '''Command line utility entry point.

    Args:
        args (list): A list of program arguments. Defaults to sys.argv.
    '''
    args = args_init(args)

    try:
        if args.port is not None:
            ping = cping.PingTCP(port=args.port, interval=args.interval)
        else:
            ping = cping.PingICMP(interval=args.interval)

        if args.layout == 'legacy':
            layout = cping.LayoutLegacy(ping)
        else:
            layout = cping.LayoutModern(ping)

        for host in args.host:
            layout.add_host(host)

        cping.utils.stagger_start(layout.hosts, layout.protocol.interval)
        layout()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()  # pragma: no cover
