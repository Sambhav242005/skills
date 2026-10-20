#!/usr/bin/env python3
"""Local Routing Harness reports. Python 3.10+, standard library only."""
import sys
sys.dont_write_bytecode = True
from routing_dashboard.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
