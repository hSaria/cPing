# cPing

[![Build status](https://img.shields.io/github/workflow/status/hSaria/cPing/CI/master)](https://github.com/hSaria/cPing/actions?query=workflow%3ACI)
[![Coverage status](https://coveralls.io/repos/github/hSaria/cPing/badge.svg)](https://coveralls.io/github/hSaria/cPing)
[![PyPI version](https://badge.fury.io/py/cping.svg)](https://badge.fury.io/py/cping)


cPing concurrently checks if hosts are responding using ICMP echo or TCP SYN.

## Installation

    pip3 install cping

## Usage

    cping host1 host2

![alt text](https://github.com/hSaria/cPing/raw/master/.github/example_1.png "Example output")

## Help

See the available arguments to adjust the behavior of cPing or use a different protocol.

    cping -h

### Unprivileged ICMP Sockets

If you're getting a `Permission denied` exception, it is likely that your OS is
too old to have [unprivileged ICMP sockets](https://fedoraproject.org/wiki/Changes/EnableSysctlPingGroupRange#Detailed_Description) enabled by default. You can enable
this with:

```shell
sudo sh -c 'echo net.ipv4.ping_group_range = 0 2147483647 >> /etc/sysctl.conf'
sudo sysctl -p
```
