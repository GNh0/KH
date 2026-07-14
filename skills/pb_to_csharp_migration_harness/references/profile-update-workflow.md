# Packaged Profile Update Workflow

This is an explicitly named maintenance workflow. It never runs during normal generation.

Normal PB-to-C# generation uses only `packaged-style-contract.md` and `packaged-style-contract.json` for style. It does not connect to a database, open or export a PBL, invoke ORCA or PblScripter, or scan local C#, Designer, SQL, PB, backup, or sibling source trees.

## Trigger

Run this workflow only when the user explicitly asks to refresh, rebuild, or audit the packaged style profile. A migration request, missing identifier, low-confidence generation result, or unavailable local artifact is not an implicit update request.

Record:

- explicit profile-update authorization;
- approved evidence roots and systems;
- read/write boundaries;
- credential-presence checks without printing secret values;
- output location outside source trees;
- sanitization and review owners.

## Maintenance Sequence

1. Create an isolated maintenance workspace and keep source systems read-only.
2. Inventory approved evidence with bounded counts before reading content.
3. For database evidence, query only approved metadata and definitions needed to derive style. Never package connection details, database names, object names, authors, values, or query-result snapshots.
4. For PBL evidence, select a matching runtime and use PblScripter or direct ORCA only after the library lineage is confirmed.
5. List objects before export, export only approved object types, and write exports to the maintenance output directory, never beside the source PBL.
6. For pre-exported PB text, trace event, retrieve, update, popup, and DataWindow relationships only within the approved export set.
7. For C# and Designer evidence, scan only approved primary files. Exclude backups, generated outputs, build folders, and current repair targets.
8. For SQL evidence, analyze procedure shape, caller parameters, branch conventions, result shape, transaction/error patterns, and formatting families without retaining concrete schema identifiers.
9. Derive generalized frequencies and conflicts, then choose conservative style families. Counts are maintenance evidence only and are not packaged.
10. Convert observations into grammars, abstract event/method shapes, provider fallbacks, property rules, grid/repository conventions, caller/SP rules, forbidden patterns, and evidence requirements.
11. Replace every concrete identifier with a placeholder or clearly synthetic identifier before editing the packaged contract.
12. Run privacy, structure, smoke, demo, and packaging tests. Require independent review before release.

## Sanitization Gate

The packaged output must contain none of the following:

- absolute or user-specific paths;
- database or server names;
- people, author tags, or account names;
- concrete program, procedure, table, column, or control instance names;
- source hashes, line counts, snapshot dates, source roots, or file fingerprints;
- raw SQL/PB/C#/Designer excerpts from the evidence set;
- credentials, connection strings, machine configuration, or license data;
- evidence-set counts that can identify a private source snapshot.

Keep only generalized behavior. Use placeholders such as `<Feature>`, `<Role>`, `<Field>`, and `<Operation>`, or neutral synthetic examples that cannot be mapped back to the evidence set.

## Provider Handling

For PblScripter and direct ORCA, use the same bounded operations: list, export selected object, export linked DataWindows, close session, and verify encoding. Match the ORCA/runtime generation to the PBL lineage. Unknown lineage permits identification/probe work only; it does not authorize conversion or parity claims.

Treat binary strings, object names, screenshots, and stale notes as weak maintenance evidence. They may identify what to inspect next but must not teach concrete identifiers to the packaged contract.

## Update Outputs

- updated `packaged-style-contract.md`;
- updated `packaged-style-contract.json` with the same contract identifier or an intentional version change;
- a private, non-packaged maintenance report recording evidence and review decisions;
- smoke/demo/packaging test results;
- a history-risk note stating whether removed private material remains in repository history.

Raw exports, database results, scan inventories, and fingerprints remain outside the package and outside normal generation inputs. Delete or retain them only under the user's approved maintenance retention policy.
