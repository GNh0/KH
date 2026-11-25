"""Export the shared KH roles as actual Codex custom-agent definitions."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common.output import configure_utf8_streams
from src.maintenance.agents import export_agents


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True,
                        help='absolute destination; .codex/agents for a project or ~/.codex/agents for personal installation')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(export_agents(Path(__file__).resolve().parents[1], args.output), ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'status': 'error', 'message': str(error)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    configure_utf8_streams()
    raise SystemExit(main())
