"""Extract SQL candidates from one exact textual PB export; no ORCA/DB execution."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from src.common.files import read_file
from src.common.output import configure_utf8_streams
from src.sql.pb_extract import extract_powerbuilder_sql_fragments

if __name__ == '__main__':
    configure_utf8_streams()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    parser.add_argument('--encoding', default='utf-8-sig')
    args = parser.parse_args()
    snapshot = read_file(args.input)
    print(json.dumps({'path': str(snapshot.path), 'sha256': snapshot.sha256,
                      'sql_candidates': extract_powerbuilder_sql_fragments(snapshot.text(args.encoding), source_name=str(snapshot.path)),
                      'not_checked': ['PB dynamic SQL assembly', 'database execution', 'unprovided linked objects']}, ensure_ascii=False, indent=2))
