"""Exchange one Google Antigravity hook event. The plugin host sets cwd to the package."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common.output import configure_utf8_streams
from src.runtime.antigravity import handle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('event', choices=['PreInvocation', 'PreToolUse', 'PostToolUse', 'Stop'])
    name = parser.parse_args().event
    raw = sys.stdin.buffer.read(8 * 1024 * 1024 + 1)
    try:
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError('event too large')
        payload = json.loads(raw.decode('utf-8-sig'))
        output = handle(name, payload)
    except (ValueError, OSError, TypeError, RuntimeError, sqlite3.Error) as exc:
        # Report a hook failure to the host log. Never echo prompts, paths or tool arguments.
        print('KH Antigravity hook unverified: ' + type(exc).__name__, file=sys.stderr)
        output = {'decision': 'allow'} if name == 'PreToolUse' else {}
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    configure_utf8_streams()
    raise SystemExit(main())
