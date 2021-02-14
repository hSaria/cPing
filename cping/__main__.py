"""Command line script."""
import argparse
import sys

import cping
import cping.layouts

INTERVAL_MINIMUM = 0.1


def args_init(args=None):
    """Returns the parsed arguments (an instance of argparse.Namespace).

    Args:
        args (list): A list of program arguments, Defaults to sys.argv.
    """
    formatter = lambda prog: argparse.HelpFormatter(prog, max_help_position=26)
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

    Returns:
        A string indicating status/error. Otherwise, returns None. It is meant to
        be used as sys.exit(cping.__main__.main()).
    """
    args = args_init(args)

    try:
        if args.port is not None:
            ping = cping.PingTCP(port=args.port, interval=args.interval)
        else:
            ping = cping.PingICMP(interval=args.interval)

        layout = cping.LayoutLegacy(ping)

        for host in args.host:
            layout.add_host(host)

        cping.protocols.stagger_start(layout.hosts, layout.protocol.interval)
        layout()
    except KeyboardInterrupt:
        pass
    except (TypeError, ValueError) as exception:
        return str(exception)
    finally:
        if 'layout' in locals():
            for host in layout.hosts:
                host.stop()

    return None


if __name__ == '__main__':
    sys.exit(main())
