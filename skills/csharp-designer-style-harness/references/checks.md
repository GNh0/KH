# Optional C# static checks

Result `status=passed` means no errors were found in the items checked. C# results show `review_status=needs_review` when warnings exist, otherwise `static_checks_only`, and explicitly report `project_style_verified=false`. They do not determine task completion. Do not use a passing result to skip comparison with current user requirements, event state, APIs, or save contracts.

`comparison_baselines` records whether originals were supplied. A single-file check without an original does not verify changes or preservation. C#/Designer/SQL treat the same file as original and candidate, including links to the same file, as an input error. Use pre-change copies or the user's specified actual migration source. A post-change copy labeled original does not establish preservation. Separate legitimate copies with identical content can be compared, but the checker does not certify their creation time or provenance.

Run `python <plugin-root>/scripts/kh_check.py csharp <absolute-source.cs> [--designer <absolute-Designer.cs>] [--original <absolute-before.cs>]` to check static UI ownership, event references, and local code changes.

Apply [user-control rules](user-controls.md) outside grids too. Review agreed Spin/ymd/pn/grd/gvw/col/rps naming for new controls, member/Name mismatches, and added DateEdit EditFormat/input masks. Repeated `--control-source <absolute-control.cs>` arguments supply current project user-control implementations, enabling type-selection/default-override checks from inheritance declarations and direct parameterless-constructor assignments regardless of library name. Both C# and Designer commands support this. Do not claim automatic validation for missing source, helpers, conditions, or dynamic values.

Missing braces in new/changed if/else/for/foreach/while/do bodies produce `control_body_braces` warnings, including one-line returns; else if chains and the while condition following do are distinguished. Strings/comments are not code, but executable code inside interpolation is checked. Statements unchanged from the original are not flagged for wholesale cleanup. Preprocessor branches are not evaluated, and syntax validity of incomplete/unsupported statements is not established. This is not a formatter that verifies all line layout, naming, explicit types, helper structure, or other coding style.

Supply explicitly preserved Designer properties through a separate comparison command. Running only `csharp --designer` does not establish their preservation.

```powershell
python <plugin-root>/scripts/kh_check.py designer <absolute-after.Designer.cs> --original <absolute-before.Designer.cs> --preserve-property txtState.Text --preserve-property txtState.Visible
```

Repeat `--preserve-property` as needed. Add `--code-behind <absolute-source.cs>` to check event implementations too. String line breaks are part of the value; do not arbitrarily treat LF and CRLF as equal.

For grids, review cell/header Appearance, SpinEdit EditMask, DisplayFormat FormatType/FormatString, column editing options, new OptionsBehavior, and options outside the HTML together. With an original, unchanged style is not flagged for cleanup. Removing OptionsBehavior is also reviewed as a change. Without an original, current assignments are marked for review without asserting that they were added.

```powershell
python <plugin-root>/scripts/kh_check.py designer <absolute-after.Designer.cs> --original <absolute-before.Designer.cs> --column-mode colLocked=read_only --column-mode colOpen=action --column-mode colInput=editable
```

A mismatch between explicit column modes and actual properties is a contract error. Without specified modes, checks may warn about missing ReadOnly with AllowEdit=false or unnecessary default assignments, but do not infer business editability for every column. Identify button Repositories by actual declared types, not names alone.

After confirming a current instruction or implementation necessity for changing an option, you may supply only that exact property, such as `--allow-property-change gvwList.OptionsView.ShowFooter`. No separate approval procedure or signature file is required. This excludes style warnings only; explicit column-mode/preservation contracts still apply. Use `--designer-original <absolute-before.Designer.cs>` to supply Designer originals to `csharp --designer`. The same option additions in code-behind are checked, with Spin and other types resolved from supplied Designer declarations. Controls with verified KoneLib.Controls declarations are treated as known base types; other user controls follow inheritance in supplied --control-source files. Using aliases, unsupplied arbitrary inheritance, dynamic runtime properties, and indirect variables are not resolved statically.

The checker is not a C# compiler or Visual Studio Designer. Review dynamic UI, helpers, and changes permitted by the actual project against current instructions/source. Do not turn style warnings into global prohibitions or separate signed approvals. Check complex data paths and DB behavior using actual source and tools.

LINQ candidates and changes between transaction-method name families are review warnings. Method names alone do not establish LINQ extension calls or lost transactions; inspect actual declarations, arguments, wrapper bodies, and framework APIs. Explicitly preserved Designer properties are compared at statement boundaries, and regular/verbatim/raw constant strings by value. Semantic equivalence of dynamic expressions is outside scope.

## Reviewing new event/data handling

C# checks compare current methods with originals and warn about these candidates. Unchanged existing handling is preserved; calls moved to another event or reintroduced are also reviewed.

- `new_ui_data_helper`: newly declared query, selected-row, or table-cloning wrappers, distinguished from implementing an existing empty method body.
- `entry_query_review`: queries added to NewCommand/EditCommand-like events. Do not automatically remove them: some, such as empty-table schema queries, may be necessary.
- `save_gate_review`: messages and return conditions added to save events/CallSaveProcedure. Compare with existing validation/failure handling and current requests.
- `manual_selected_row_delete`, `client_sequence_review`, `row_header_propagation_review`: manual selected-row deletion, numbering candidates using RowVersion/maxima, and header/context fields copied into new rows. Inspect actual API and XML/SP responsibilities.
- `date_helper_review`: direct DateTime.Today/Now assignments when the same original member uses SetToDay or its actual type supplied through `--control-source` provides SetToDay(int). Do not guess unsupplied APIs.
- `ui_state_policy_review`: bool fields newly used for edit mode, Enabled/ReadOnly, input cancellation, control protection, or event restrictions. Review existing fields too when restriction sites change. Compare declarations, initialization, query assignments, and usages; distinguish renames from actual policy changes. Constants, readonly fields, and simple local bools are excluded from this candidate.

These structure-aware warnings do not prohibit all validation, loops, helpers, or requerying. They do not automatically resolve method aliases, indirect calls, local-function bodies, conditional execution order, or actual server numbering/required fields. Complete preservation of original commented bodies is also outside this check; compare those requests against actual bodies separately. Comparing added helpers requires `--original`. Supply required actual control source through existing `--control-source` arguments without asking the user for new profiles or approval files.

## Preserving original Designer properties

For migrations preserving the original, supply C# `--original` and `--designer-original`, then use `--preserve-existing` to compare explicit assignments on retained controls and the form. The standalone Designer command also supports `--original` and `--preserve-existing`. Repeat `--member-rename oldName=newName` for renames. Example:

```text
python <plugin-root>/scripts/kh_check.py csharp <after.cs> --original <source.cs> --designer <after.Designer.cs> --designer-original <source.Designer.cs> --preserve-existing --member-rename txt_old=txtOld
```

Rename mappings apply in memory to identifiers, Name, and direct resources.GetObject/GetString keys without modifying actual originals. Ordinary Text/BindingField strings remain unchanged even when equal to a name. Missing original members, duplicate targets, and original-member collisions are errors.

Read `designer_preservation` for compared-member counts, property differences, unmatched original members, and new members. Differences produce per-control `designer_existing_properties_changed` warnings. For requested binding/location changes or similar needs, you may specify `--allow-property-change currentMember.Property` based on the actual request. Address form properties as, for example, `form.ClientSize`. Exemptions are not completed verification and do not erase explicit `--preserve-property` errors.

Deletions/new controls are not automatically authorized. Compare unmatched lists against requested deletions/additions and resx references. If all names differ and nothing can be compared, the result is incomplete. Separately check collection Add/AddRange, initialization order, conditional/indirect assignments, actual resource contents, and runtime behavior.

## Actual numeric columns and check exemptions

Repeat --numeric-column colList_QTY on C#/Designer commands to check actual numeric columns' Spin Repository connections. Do not infer numeric types from field names; explicitly requested connections are checked even when unchanged. The csharp --designer command also checks explicit code-behind ColumnEdit overwrites. The designer command checks numeric connections in supplied Designer assignments. Static checks do not establish conditional execution or dynamic column creation.

--allow-property-change records excluded scope in style_exemptions and not_checked. Do not copy the change list into exemptions just to pass. The option establishes neither user authorization nor necessity for a disfavored approach, and does not override explicit preservation contracts such as --preserve-property.

After verifying a current explicit request for matching numeric display on a target without shared initialization and the actual original settings, you may exempt only that Repository's exact DisplayFormat.FormatString/FormatType properties. Distinguish this from unnecessary default additions. The checker does not automatically determine shared-helper calls or the latest conversation request; verify that evidence and scope separately. Exclusion results do not replace that evidence.

For a full style review, consider both original-preservation comparison and standalone candidate style checks. Unchanged existing code in a diff check does not establish correct braces, naming, or connections throughout the source. Honor both the style-edit scope and preservation of user changes.

## Numeric format notation and placement

numeric_format_preference flags new N0/N2/Nn formats for review. It checks direct FormatString/DisplayFormat/EditMask assignments, composite formats in GridColumnSummaryItem/GridGroupSummaryItem constructors, ToString's first format argument, string.Format, and static interpolation format specifiers. Plain N0 in strings/comments and escaped braces are not treated as format usage. With an original, existing occurrence counts in the same context/format are excluded; existing files are not automatically modified.

Unknown format variables, concatenations, custom formatters, and actual overload types are not resolved. string.Format culture overloads are distinguished only for directly visible CultureInfo arguments. The check does not establish whether an ordinary C# string variable is numeric. Even when custom-format candidates are suggested, compare zero, fixed-decimal, culture, and rounding semantics.

SummaryItem.DisplayFormat is a summary format and is distinguished from ordinary-cell display_format_preference checks. Column/Repository DisplayFormat still undergoes default-property review even with a # format. --allow-property-change excludes a property's default-style check only; it does not create a requirement for N formats, and numeric-notation review remains separate.

Do not report style compliance from status=passed and exit code 0 alone. For display_format_preference, compare current user exclusions, setting locations, and actual initialization. Spin-connection or decimal-display issues do not arbitrarily justify adding properties.
