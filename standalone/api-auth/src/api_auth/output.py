"""UTF-8 CLI output without a dependency on KH."""
from io import TextIOWrapper
import sys


def configure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, TextIOWrapper):
            stream.reconfigure(encoding='utf-8')
