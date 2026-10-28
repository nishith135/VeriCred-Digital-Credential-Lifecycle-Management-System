"""Helper to run pip inside virtual environment with IPv4 address family forced.

Resolves Windows IPv6 routing timeouts during package installation.
"""

import socket
import sys

# Patch socket.getaddrinfo to filter for AF_INET (IPv4)
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_getaddrinfo(*args, **kwargs):
    responses = _orig_getaddrinfo(*args, **kwargs)
    v4 = [r for r in responses if r[0] == socket.AF_INET]
    return v4 if v4 else responses


socket.getaddrinfo = _ipv4_getaddrinfo

# Now invoke pip CLI
from pip._internal.cli.main import main

if __name__ == "__main__":
    args = sys.argv[1:] if len(sys.argv) > 1 else ["install", "-r", "requirements.txt"]
    sys.exit(main(args))
