"""Compatibility module for the shared, read-only SQL command."""
from scripts.kh_check import main

if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main(['sql', *sys.argv[1:]]))
