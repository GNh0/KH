"""One bounded UTF-8 JSON exchange per host event; no persistent runtime."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common.output import configure_utf8_streams
from src.runtime.hooks import handle


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', choices=['codex', 'claude'], required=True)
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.buffer.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError('hook input exceeds 8 MiB; event unverified')
        event = json.loads(raw.decode('utf-8-sig'))
        if not isinstance(event, dict):
            raise ValueError('hook input must be an object')
        output = handle(event, args.host)
    except Exception as exc:
        # Do not expose tool input/credentials in a traceback or pretend a hook failure enforced a rule.
        output = {'systemMessage': 'KH hook unavailable (' + type(exc).__name__ + '); this event is unverified. Use the skill procedure directly.'}
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    configure_utf8_streams()
    raise SystemExit(main())
