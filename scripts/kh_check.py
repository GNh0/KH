"""Run optional KH checks from any working directory without installing a server."""
from pathlib import Path
import sys

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))


def main(argv=None):
    import argparse
    from src.common.files import read_file
    parser = argparse.ArgumentParser(description="KH source and artifact checks; no agent orchestration or DB access")
    commands = parser.add_subparsers(dest="command", required=True)
    sql = commands.add_parser("sql", help="compare/inspect SQL or normalize supported layout")
    sql.add_argument("input")
    sql.add_argument("candidate", nargs="?")
    sql.add_argument("--preserve-aliases", action="store_true")
    sql.add_argument("--normalize-layout", action="store_true")
    sql.add_argument("--check-delta", action="store_true")
    cs = commands.add_parser("csharp", help="inspect current C# and optional Designer/baseline")
    cs.add_argument("input")
    cs.add_argument("--original")
    cs.add_argument("--designer")
    cs.add_argument('--designer-original')
    designer = commands.add_parser('designer', help='compare explicit Designer properties with a supplied baseline')
    designer.add_argument('input')
    designer.add_argument('--original')
    designer.add_argument('--code-behind')
    designer.add_argument('--preserve-property', action='append', default=[])
    for command in (cs, designer):
        command.add_argument('--column-mode', action='append', default=[], metavar='MEMBER=MODE',
                             help='explicit column contract: read_only, action, or editable')
        command.add_argument('--allow-property-change', action='append', default=[], metavar='MEMBER.PROPERTY',
                             help='specific current requirement; suppresses its default-style warning')
    sp = commands.add_parser('sp-call', help='compare one selected C# call with one actual procedure definition')
    sp.add_argument('input')
    sp.add_argument('procedure')
    pb = commands.add_parser("pb", help="inspect a supplied PB export")
    pb.add_argument("input")
    pb.add_argument("--encoding", default="utf-8-sig")
    artifact = commands.add_parser("artifact", help="check a file's structure, not its visual rendering")
    artifact.add_argument("input")
    package = commands.add_parser("package", help="validate local plugin files and imports")
    package.add_argument("input")
    args = parser.parse_args(argv)
    try:
        column_modes = {}
        for item in getattr(args, 'column_mode', []):
            name, separator, mode = item.partition('=')
            if not separator or not name or mode not in {'read_only', 'action', 'editable'}:
                raise ValueError('--column-mode requires MEMBER=read_only, MEMBER=action, or MEMBER=editable')
            if name in column_modes and column_modes[name] != mode:
                raise ValueError('Conflicting column modes for ' + name)
            column_modes[name] = mode
        if args.command == "sql":
            from src.sql.checks import check_sql
            from src.sql.layout import normalize_sql_join_layout
            original = read_file(args.input).text()
            if args.normalize_layout:
                if args.candidate:
                    parser.error("--normalize-layout accepts one input")
                print(normalize_sql_join_layout(original), end="")
                return 0
            candidate = read_file(args.candidate).text() if args.candidate else original
            result = check_sql(candidate, original=original if args.candidate else None,
                               preserve_aliases=args.preserve_aliases, check_delta=args.check_delta)
        elif args.command == "csharp":
            from src.csharp.checks import check_csharp
            result = check_csharp(read_file(args.input).text(),
                                   original=read_file(args.original).text() if args.original else None,
                                   designer=read_file(args.designer).text() if args.designer else None,
                                   original_designer=read_file(args.designer_original).text() if args.designer_original else None,
                                   column_edit_modes=column_modes, allowed_property_changes=args.allow_property_change)
        elif args.command == 'designer':
            from src.csharp.designer import check_designer
            result = check_designer(read_file(args.input).text(),
                original=read_file(args.original).text() if args.original else None,
                code_behind=read_file(args.code_behind).text() if args.code_behind else '',
                preserved_properties=args.preserve_property, column_edit_modes=column_modes,
                allowed_property_changes=args.allow_property_change)
        elif args.command == 'sp-call':
            from src.pb.sql import check_sp_call
            result = check_sp_call(read_file(args.input).text(), read_file(args.procedure).text())
        elif args.command == "pb":
            from src.pb.checks import check_pb_export
            result = check_pb_export(read_file(args.input).text(args.encoding), path=args.input)
        elif args.command == "artifact":
            from src.artifacts.checks import check_artifact
            result = check_artifact(args.input)
        else:
            from src.maintenance.package_check import check_package
            result = check_package(args.input)
        print(result.to_json())
        return result.exit_code
    except (OSError, ValueError, UnicodeError) as error:
        from src.common.results import CheckResult, Issue
        result = CheckResult(issues=[Issue("input_error", "error", str(error))])
        print(result.to_json())
        return result.exit_code


if __name__ == "__main__":
    from src.common.output import configure_utf8_streams
    configure_utf8_streams()
    raise SystemExit(main())
