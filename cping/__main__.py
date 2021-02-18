"""Command line script."""
import argparse
import sys

import cping
import cping.protocols

INTERVAL_MINIMUM = 0.1


def args_init(args=None):
    """Returns the parsed arguments (an instance of argparse.Namespace).

    Args:
        args (list): A list of program arguments, Defaults to sys.argv.
    """
    formatter = lambda prog: argparse.HelpFormatter(prog, max_help_position=30)
    parser = argparse.ArgumentParser(formatter_class=formatter)

    parser.add_argument('host',
                        type=str,
                        nargs='+',
                        help='one or more hosts to ping')

    parser.add_argument('-i',
                        '--interval',
                        metavar='sec',
                        type=float,
                        help='ping interval (default: %(default)s)',
                        default=1)

    # Suppress the layout option on Windows as it's currently limited to modern
    layout_help = argparse.SUPPRESS

    if sys.platform != 'win32':
        layout_help = ('display format. choices: %(choices)s '
                       '(default: %(default)s)')

    parser.add_argument('-l',
                        '--layout',
                        metavar='name',
                        type=str.lower,
                        help=layout_help,
                        choices=['legacy', 'modern'],
                        default='modern')

    parser.add_argument('-p',
                        '--port',
                        metavar='port',
                        type=int,
                        help='test using TCP SYN (default: ICMP echo)')

    args = parser.parse_args(args=args)

    if args.interval < INTERVAL_MINIMUM:
        parser.error('minimum interval is {}'.format(INTERVAL_MINIMUM))

    return args


def main(args=None):
    """Command line utility entry point.

    Args:
        args (list): A list of program arguments. Defaults to sys.argv.
    """
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

        cping.protocols.stagger_start(layout.hosts, layout.protocol.interval)
        layout()
    except KeyboardInterrupt:
        pass
    finally:
        if 'layout' in locals():
            for host in layout.hosts:
                host.stop()


if __name__ == '__main__':
    main()  # pragma: no cover
