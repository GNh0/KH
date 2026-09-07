"""Compatibility module for the shared, read-only SQL command."""
from scripts.kh_check import main
from src.common.output import configure_utf8_streams

if __name__ == '__main__':
    import sys
    configure_utf8_streams()
    raise SystemExit(main(['sql', *sys.argv[1:]]))
