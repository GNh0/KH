# Illustrative SELECT/SAVE patterns

All schemas, identifiers, values and messages below are fictional. These examples express the user's preferred structures; they are not application code or deployable procedure templates. Derive actual types, keys, state strings and transaction ownership from the target and complete approved comparison procedures.

Read the sections matching the changed responsibilities, not every example. Each section pairs a specific misuse to avoid with the intended structure. Do not copy a fictional eligibility rule, state value or validation into an unrelated program.

| Responsibility | Example |
| --- | --- |
| Descriptive lookup versus required row eligibility | [SELECT: lookup and eligibility](select-patterns.md#lookup-and-eligibility) |
| One header row with detail totals | [SELECT: grouped detail JOIN](select-patterns.md#grouped-detail-join) |
| Exclude rows already processed | [SELECT: exclusion JOIN](select-patterns.md#exclusion-join) |
| Multiple ordered results for one mode | [SELECT: one branch with multiple results](select-patterns.md#one-branch-with-multiple-results) |
| XML parsing and NEW INSERT SELECT | [SAVE: parsed rows and NEW](save-patterns.md#parsed-rows-and-new) |
| Modify/delete selected input rows | [SAVE: MOD and DEL](save-patterns.md#mod-and-del) |
| Delete several complete master documents | [SAVE: multiple-master-delete](save-patterns.md#multiple-master-delete) |
| Validate related-row existence | [Validation: missing related row](validation-patterns.md#missing-related-row) |
| Validate a complete edited quantity proposal | [Validation: edited-quantity-proposal](validation-patterns.md#edited-quantity-proposal) |

For nested FROM/UNION blocks and grouped INSERT/SELECT text-column alignment, use the existing [SQL layout examples](style.md); keep the query's actual keys and row grain separate from its whitespace layout.

Necessary numbering/output variables and staging updates that record generated keys remain valid when the real flow needs them. Do not judge necessity from variable count or ban every staging UPDATE.

Before applying a draft and after the final edit, compare the exact affected bodies with the matching examples and complete references. Include existing code the user asked to correct. A final edit reopens the affected comparison and audit.
