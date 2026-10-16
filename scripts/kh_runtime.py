"""Run an owned Windows command tree without leaving helper descendants behind."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv: list[str] | None = None) -> int:
    from src.runtime.windows_job import run_owned
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cwd', help='existing absolute working directory')
    parser.add_argument('--timeout', type=float, help='optional positive lifetime in seconds')
    parser.add_argument('command', nargs=argparse.REMAINDER, help='-- executable arguments; no existing PID/name cleanup')
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    try:
        result = run_owned(command, cwd=args.cwd, timeout=args.timeout)
        print('KH_RUNTIME_RESULT=' + json.dumps(asdict(result)), file=sys.stderr, flush=True)
        return result.exit_code if result.cleanup_verified else 125
    except (OSError, ValueError) as error:
        print('KH_RUNTIME_RESULT=' + json.dumps({'status': 'failed', 'cleanup_verified': False,
                                                'error': str(error)}, ensure_ascii=False), file=sys.stderr, flush=True)
        return 125


if __name__ == '__main__':
    raise SystemExit(main())
