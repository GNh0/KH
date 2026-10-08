# Optional C# static checks

Result `status=passed` means no errors were found in the items checked. C# results show `review_status=needs_review` when warnings exist, otherwise `static_checks_only`, and explicitly report `project_style_verified=false`. They do not determine task completion. Do not use a passing result to skip comparison with current user requirements, event state, APIs, or save contracts.

`comparison_baselines` records whether originals were supplied. A single-file check without an original does not verify changes or preservation. C#/Designer/SQL treat the same file as original and candidate, including links to the same file, as an input error. Use pre-change copies or the user's specified actual migration source. A post-change copy labeled original does not establish preservation. Separate legitimate copies with identical content can be compared, but the checker does not certify their creation time or provenance.

Choose comparison scope from the task. An ordinary local edit uses the pre-change target to review new changes. A new screen import or requested whole-file style correction also needs a standalone candidate inspection with the actual control sources and same-project Designer reference. An imported foreign C# file can establish behavior/provenance but cannot establish the target's coding style. Differential checks suppress unchanged findings; do not treat that suppression as a full style pass. After repeated style feedback, review the affected C#, Designer, bindings and SP paths together and resolve relevant warnings against actual requirements before reporting completion.

Run `python <plugin-root>/scripts/kh_check.py csharp <absolute-source.cs> [--designer <absolute-Designer.cs>] [--original <absolute-before.cs>]` to check static UI ownership, event references, and local code changes.

Apply [user-control rules](user-controls.md) outside grids too. Review agreed Spin/ymd/pn/grd/gvw/col/rps naming for new controls, member/Name mismatches, and added DateEdit EditFormat/input masks. Repeated `--control-source <absolute-control.cs>` arguments supply current project user-control implementations, enabling type-selection/default-override checks from inheritance declarations and direct parameterless-constructor assignments regardless of library name. Both C# and Designer commands support this. Do not claim automatic validation for missing source, helpers, conditions, or dynamic values.

For new controls with a constructor `Size`, `user_control_size_shrink` checks arbitrary shrinking. Width may grow for content. Label height is compared with actual screen controls, rather than treating every height increase as allowed. An explicit user-requested size can be exempted with `--allow-property-change member.Size` after checking that request; this option alone is not proof of authorization. The check does not impose one global size or rewrite unchanged retained controls.

With actual `--control-source` and `--style-reference-designer` inputs, added/edited labels use their constructor font/alignment and the actual similar labels/inputs' heights. The self-property `Default ? Far/Center : same-property` constructor fallback establishes ordinary alignment. Literal differences such as Font size 10/10F and qualified/unqualified enum names are equivalent. Proved differences produce `label_font_mismatch`, `label_alignment_mismatch`, `label_height_mismatch` or `control_height_mismatch` errors; inconsistent references or unsupported values make the result incomplete. Constructor dimensions alone do not prove a serialized screen height. `csharp --designer` also checks explicit code-behind overrides using the Designer's actual control types. Helpers, conditional execution and final rendering still require source/visual review.

Supply `--style-reference-designer <absolute-existing-screen.Designer.cs>` with `designer` or `csharp --designer` when creating a screen from an actual same-project example. It reviews new LookUpEdit/DateEdit/SpinEdit `Properties.Buttons` and DateEdit `CalendarTimeProperties.Buttons` calls. `--original`/`--designer-original` separately compare retained controls; the style reference cannot replace that baseline. Missing button setup is a review warning because actual item counts, indirect initialization and rendered visibility remain outside this static check. Labels also compare `Appearance.Options.UseTextOptions`: an inherited established value counts, a proved difference is an error, and a missing unresolved effective value makes the result incomplete. Without a reference, screen comparison is explicitly listed in `not_checked`. Resolve findings against actual initialization and the screen before completion.

`editor_button_initialization_removed` also reviews vanished button-initializer paths on retained members against an original, even without a style reference. Compare actual constructor/shared initialization and the requested edit before removing an existing initializer. The check does not evaluate collection contents or certify runtime item counts.

Comparison also covers LookUp/Date/Spin RepositoryItems with their direct `Buttons` and `CalendarTimeProperties.Buttons` initializer paths. It uses the actual supplied reference rather than assuming every Repository has the same default button.

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

### Comparing project command phases and requested operations

Supply `--style-reference-csharp <absolute-same-project-screen.cs>` to compare recognizable Save/New operations and CallSaveProcedure transport with the actual reference bodies. This is separate from `--original`, which establishes change provenance. Read the reference first and select one with a matching screen flow; the checker cannot verify its project, relevance or provenance. It does not make one screen's pattern universal.

Repeat `--screen-command` for the operations permitted by the latest request. For a modify-only screen with search, edit, save and cancel, use:

```text
python <plugin-root>/scripts/kh_check.py csharp <candidate.cs> --style-reference-csharp <same-project-screen.cs> --screen-command search --screen-command edit --screen-command save --screen-command clear
```

`print` is also supported as an explicit screen operation.

- `screen_command_out_of_scope`: a direct subscription to an excluded screen command is an error. Check inherited toolbar availability separately. Nonempty recognizable handlers without such a subscription produce `screen_command_body_out_of_scope` review warnings; an empty unwired handler does not imply an implemented feature.
- `command_phase_drift_review`: Save adds AcceptChanges, DEFAULT mode assignment or Usr_ControlsProtect, or New adds OpenMenuProgram, beyond occurrences in the corresponding reference command. Review their purpose and phase; none of these operations is globally prohibited. Other reference phases are reported as context. A legitimate reset already present in reference Save is retained.
- `save_refresh_drift_review`: the reference Save dispatches Search but the candidate Save does not. Trace valid indirect refresh/tab paths before changing code.

`command_flow` reports the supplied operation scope, reference command kinds and compared phases; `comparison_baselines.command_style_reference` records reference availability. Missing or ambiguous reference bodies, unsupported expression-bodied handlers, indirect calls/subscriptions and XML/SP behavior remain in `not_checked`. Comments, literal strings and uncalled local-function bodies are excluded from recognizable operation counts. General branch feasibility and operation arguments are not resolved.

With `--original`, unchanged command bodies are excluded from phase-style review, while explicit command scope still applies. New imports/full style corrections also need standalone inspection. Without the corresponding inputs, neither requested operation scope nor project command phases are verified. Resolve warnings against the current user request and actual helper/base path; do not add exemptions or blindly copy the reference to get a pass.

The same reference also compares a uniquely recognizable CallSaveProcedure body:

- `save_xml_contract_drift_review`: the reference directly serializes DataTable XML while the candidate save does not.
- `rowwise_save_contract_drift_review`: an XML reference has fewer direct CallSaveProcedure calls inside loops than the candidate, including Print handlers.
- `save_output_contract_drift_review`: the candidate save adds Output/InputOutput directions beyond the reference. Verify actual value ownership and refresh needs.

`save_contract_comparison` reports available bodies and comparison coverage. Unchanged original methods, comments, strings and uncalled local functions are excluded from new findings. Missing/ambiguous or expression-bodied save methods, indirect helper calls, XML contents/row-state correctness and SP behavior remain unverified. These are review differences, not universal bans on scalar saves, loops or outputs.

C# checks compare current methods with originals and warn about these candidates. Unchanged existing handling is preserved; calls moved to another event or reintroduced are also reviewed.

- `new_ui_data_helper`: newly declared query, selected-row, or table-cloning wrappers, distinguished from implementing an existing empty method body.
- `entry_query_review`: queries added to NewCommand/EditCommand-like events. Do not automatically remove them: some, such as empty-table schema queries, may be necessary.
- `save_gate_review`: messages and return conditions added to save events/CallSaveProcedure. Compare with existing validation/failure handling and current requests.
- `manual_selected_row_delete`, `client_sequence_review`, `row_header_propagation_review`: manual selected-row deletion, numbering candidates using RowVersion/maxima, and header/context fields copied into new rows. Inspect actual API and XML/SP responsibilities.
- `date_helper_review`: direct DateTime.Today/Now assignments when the same original member uses SetToDay or its actual type supplied through `--control-source` provides SetToDay(int). Do not guess unsupplied APIs.
- `ui_state_policy_review`: bool fields newly used for edit mode, Enabled/ReadOnly, input cancellation, control protection, or event restrictions. Review existing fields too when restriction sites change. Compare declarations, initialization, query assignments, and usages; distinguish renames from actual policy changes. Constants, readonly fields, and simple local bools are excluded from this candidate.
- `save_worktype_literal_review`: a directly named DbParameter/SqlParameter supplies a literal mode in a recognized save boundary. Verify the actual mode API and SP operation; dynamic values and indirect save wrappers remain unverified.
- `manual_original_row_comparison_review`: several Original field values are compared before skipping a row in a save. This does not reject deleted-row Original key access.
- `new_edit_commit_call`: PostEditor/UpdateCurrentRow candidates in standalone inspection as well as new calls in a differential check. Inspect the actual editor/save lifecycle before retaining or removing them.
- `input_tag_binding_review`: an SP parameter uses Tag from an input control whose type is known from the supplied Designer/control sources. It does not reject button action metadata or resolve indirect code/name mappings.
- `focus_edit_gate_order_review`: a top-level negative focused-row return precedes an edit-mode guard in a recognized FocusedRowChanged method. Other event/order paths and branch feasibility need source review.
- `action_tag_case_preference`: lowercase application-code candidates in a Tag switch or a new/changed button Tag assignment. Check both sites together and preserve externally defined case-sensitive values.

These structure-aware warnings do not prohibit all validation, loops, helpers, fixed operations, Tag usage, or requerying. They do not automatically resolve method aliases, indirect calls, local-function bodies, general conditional execution order, or actual server numbering/required fields. Complete preservation of original commented bodies is also outside this check; compare those requests against actual bodies separately. Comparing added helpers requires `--original`. Supply required actual control source through existing `--control-source` arguments without asking the user for new profiles or approval files.

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
