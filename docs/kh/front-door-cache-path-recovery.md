# Front-Door Cache Path Recovery

Date: 2026-06-11

## Summary

After a KH UAF plugin upgrade, an already-running Codex session can still contain old skill root paths. In that state, the active session may try to call a removed path such as `...kh-uaf\2.9.67\skills\always_on_front_door\scripts\front_door.py` while the installed cache has already moved to `2.9.68` or later.

This is not the same as "no front-door cache exists." It is a stale session skill path.

## Findings

- The filesystem had an installed KH UAF cache at `2.9.68`.
- `always_on_front_door/scripts/front_door.py` existed under the installed `2.9.68` cache.
- A stale `2.9.67` host skill path failed because that specific version folder no longer existed.
- The previous front-door status logic marked any stale host KH cache path as `blocked`, even when a valid repo-local or current plugin-cache skill source was already available.
- A plugin-cache wrapper run could also be reported as `repo-local` because the wrapper treats its current module root as the repository root.

## Fixes

- Front-door now reports stale host skill paths as warnings when a valid current skill source is available.
- `front_door_status` remains `ok` when KH skills are resolved from repo-local source or the latest plugin cache despite a stale host path.
- The warning records the recovered source path, making the distinction clear:
  - stale host path: old session pointer
  - resolved skill source: actual source used for routing
- Plugin-cache roots under `.codex/plugins/cache/kh-uaf-marketplace/kh-uaf/<version>` are identified as `codex-plugin-cache` with the cache version.

## Regression Evidence

- `python -B -m unittest tests.test_kh_front_door.KhFrontDoorTests.test_front_door_warns_but_recovers_from_stale_host_cache_paths tests.test_kh_front_door.KhFrontDoorTests.test_cache_root_is_reported_as_codex_plugin_cache`
  - Result: 2 tests passed.
- `python -B -m unittest tests.test_kh_front_door`
  - Result: 19 tests passed.
- Manual stale path check with a removed `2.9.67` path returned:
  - `front_door_status=ok`
  - `stale_or_missing_skill_paths[0].status=stale_kh_cache_path`
  - warning showing recovery from current `repo-local` source.

## Operational Notes

- Existing live sessions can still hold stale skill root metadata until a fresh session starts.
- The fix prevents KH runtime from falsely treating that stale pointer as a missing KH installation when another valid source is available.
