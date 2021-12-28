# cPing

[![Build status](https://img.shields.io/github/workflow/status/hSaria/cPing/CI/main)](https://github.com/hSaria/cPing/actions?query=workflow%3ACI)
[![Language grade: Python](https://img.shields.io/lgtm/grade/python/github/hSaria/cPing)](https://lgtm.com/projects/g/hSaria/cPing/context:python)
[![Coverage status](https://coveralls.io/repos/github/hSaria/cPing/badge.svg)](https://coveralls.io/github/hSaria/cPing)
[![Downloads](https://static.pepy.tech/personalized-badge/cping?period=total&units=international_system&left_color=grey&right_color=brightgreen&left_text=downloads)](https://pepy.tech/project/cping)
[![PyPI version](https://badge.fury.io/py/cping.svg)](https://badge.fury.io/py/cping)

cPing concurrently checks if hosts are responding using ICMP echo or TCP SYN.

## Installation

    pip3 install cping

## Usage

cPing uses unprivileged sockets; no need for root privileges.

    cping host1 host2

![alt text](https://github.com/hSaria/cPing/raw/main/.github/example_1.png "Example output")

> Tip: When you launch cPing, look at the footer; it's got some useful actions.

## Help

See the available arguments to adjust the behavior of cPing or use a different protocol.

    cping -h

If you found a bug, or just have a question/suggestion, please open an [issue](https://github.com/hSaria/cPing/issues/new/choose) (greatly appreciated).

### Sparkline on Windows

The sparkline (right part of the screenshot) is simplified on Windows as it doesn't support the required [block characters](https://w.wiki/zKh). If you know of any substitutes, let me know.

### Unprivileged ICMP Sockets

If you're getting a `Permission denied` exception, it is likely that your OS is
too old to have [unprivileged ICMP sockets](https://fedoraproject.org/wiki/Changes/EnableSysctlPingGroupRange#Detailed_Description) enabled by default. You can enable
this with:

```shell
sudo sh -c 'echo net.ipv4.ping_group_range = 0 2147483647 >> /etc/sysctl.conf'
sudo sysctl -p
```
