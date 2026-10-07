"""Run shared source checks without imposing the personal KH style."""
from pathlib import Path
import sys

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))


def main(argv: list[str] | None = None) -> int:
    from scripts.kh_check import main as check
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] in {'sql', 'csharp', 'designer'}:
        arguments.extend(['--style-policy', 'project'])
    return check(arguments)


if __name__ == '__main__':
    from src.common.output import configure_utf8_streams
    configure_utf8_streams()
    raise SystemExit(main())
