#!/usr/bin/env python
import argparse
import sys
from .monitor import AshwamMonitor

def main():
    parser = argparse.ArgumentParser(
        description="Ashwam Production Monitoring - detect model/prompt drift and unsafe behavior"
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run monitoring analysis')
    run_parser.add_argument('--data', required=True, help='Path to data directory')
    run_parser.add_argument('--out', required=True, help='Path to output directory')
    
    args = parser.parse_args()
    
    if args.command == 'run':
        monitor = AshwamMonitor()
        monitor.run(args.data, args.out)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == '__main__':
    main()
