# Validating analysis and migration results

For detailed-plan requests, connect screens, events, DWs, DBs, fields, inputs/outputs, save order, ambiguities, and implementation order so another implementer can proceed. Do not require this document for simple query extraction.

Compare the requested flow in actual source and target: query, edit protection, new/edit/delete, XML, SP, requery/restoration, and reports. Record missing events, fields, and indirect calls as unverified. Do not encode an interpretation opposite to the user's example as a fixture expectation.

You may start static PB input analysis with `python <plugin-root>/scripts/kh_check.py pb <absolute-export>`. Its output does not replace a complete PBL or execution results. Claims of equivalent values, row counts, query counts, or performance require actual comparison conditions and results.

Supply two JSON objects to `src.pb.equivalence.compare_observations`. `parameters` is an object with string keys; `database` is a nonempty string; `schema` is an ordered JSON array; `ordered` is an actual boolean; `rows` is a JSON array of row values. Nested value types are compared too, and `true` differs from `1`. Key order is irrelevant; row duplicates are preserved, and row order is compared when `ordered=true`. Depth over 100, non-string keys, non-finite numbers, or incorrect field types produce `incomplete`.

`elapsed_ms` is a nonempty array of finite nonnegative numbers; booleans are not samples. Actual execution provenance is not automatically authenticated. Optional `query_count` and `logical_reads` are compared/reported as nonnegative integers. Without valid timing, performance is unverified. If context/results differ, a favorable speed ratio does not establish an equivalent optimization.
