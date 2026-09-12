# Behavior contracts for screen edits and repeated queries

Apply this when editing screens with multiple UserControls, monitoring, automatic queries, or grid rebinding. Do not copy one project's screen names, WORKTYPE, periods, refresh seconds, or displayed row counts into defaults for every screen.

## Current request and ownership

- If the user requests removing only wording, do not remove date inputs or settings persistence too. User-configured columns, widths, order, Font, and Visible become the baseline. Apply the latest instruction when an earlier request is corrected or canceled.
- For a request to check all of several screens, identify their actual project list. Do not edit only one screen or the initially generated code and report full application. Do not use already incorrect current source as the original merely to pass an unchanged comparison.
- If each UserControl owns its query, keep DB calls and DataTable/DataSet binding in that control. The parent form handles actual settings transfer and screen transitions. Do not centralize business queries or example data in the parent merely because wiring them there is convenient.
- Determine procedure names, WORKTYPE, parameters, and result-table order from actual definitions and latest user instructions. If asked to prepare only callers, clearly retain the unimplemented status. Do not use invented procedure names, Preview INI branches, or sample data to imply a live query is connected. For sample removal, inspect generation, return, and call branches together.

## Task management and query timing

Read the user-specified actual Task manager's APIs for execution, repetition, cancellation, duplicate execution, and UI dispatch. Do not reimplement shared functionality it already handles with per-form/control TaskCompletionSource, cancellation registrations, or repeat loops. Do not remove required UI-thread dispatch or shutdown waiting to simplify code. Do not impose one Task-versus-Timer choice on every project.

Check the separate triggers for automatic requerying, screen transitions, main-list queries, and selected-key detail queries. Do not skip periodic requerying merely because the selected page is unchanged. Required periodic refresh must occur even with only one active screen. If the request assigns list queries to screen entry and detail queries to main-key changes, preserve those roles while connecting periodic behavior. Do not replace this with forced full queries on every control each time.

During a running query, handle duplicate requests and late results from earlier requests. Match settings-dialog, pause, and shutdown behavior to actual requirements and lifetimes. Clock updates, screen transitions, and DB requerying do not share completion conditions merely because one event triggers them.

## Grid connections and overwrite paths

Identify numeric columns from actual returned types and business meaning. Check that ColumnEdit references an actual Spin Repository and that declaration, construction, and RepositoryItems registration are connected. A numeric-looking name or Repository declaration alone does not establish a complete connection. Do not turn a time display returned by SQL as a string such as HH:mm into numeric input based only on its field name.

For feedback such as “SpinEdit이 연결되지 않은 것 같다” (SpinEdit seems unconnected), inspect actual declarations, registration, ColumnEdit, and regeneration paths. Trailing decimal zeros alone do not establish a connection failure. Check value types/scales and actual control initialization; do not turn a connection-check request into a request for DisplayFormat/EditMask. If the current user explicitly excludes those properties, easier display correction does not justify an exception.

Do not explain the comparison screen's display from Designer alone. Trace shared form → control-initialization helper → Repository iteration and conditional format assignments, and check whether the target executes that path. If the user later explicitly requests the same format on a target lacking the path, follow that latest request. In audits, distinguish request order and change timing: unrequested additions before authorization and requested application afterward are not the same violation. Follow [numeric display formats](coding-style.md) for exact formats and decimal precision.

To preserve user-edited column widths, MaxWidth, AutoWidth, Font, and column lists, inspect more than Designer and initial display. Find paths that rewrite these values during Load, post-query binding, page transitions, SizeChanged, BestFitColumns, LayoutChanged, layout restoration, and dynamic column regeneration. Do not add unnecessary options or reset user edits on other screens to resolve one width issue.

When removing a mask, do not automatically replace it with properties such as DisplayFormat/EditFormat. Compare the user's scope for omitting display options against actual control/initialization-helper defaults. Verify a required display behavior or an actual initialization path; another project's helper example alone does not justify an exception for this screen.

After identifying actual numeric columns from source, optionally pass them to the checker with arguments such as --numeric-column colList_QTY. Explicit connection contracts are checked even when unchanged from the original. This does not require the user to create a new profile. After static checks, still verify final connections through runtime regeneration and selection/page/size changes.

## Query-result calculations and display

Check the specified comparison screen's actual procedures and current mode. Compare period, filter, JOIN-key, NULL-handling, and unit contracts across headers, grids, charts, and UNION branches. Condition-string counts or similar comments do not establish equal results. For reported data differences, first trace actual dates, source rows, aggregation keys, duplicates, and filters.

Calculate an overall ratio from the required numerator total and denominator total, not the simple average or sum of row ratios. Check actual zero-denominator handling, rounding, integer/decimal types, and minute/hour units. Do not reconvert in the screen values already converted by SQL. Distinguish Footer, final total-column, and header locations and percent signs as requested. Do not duplicate in C# display fields or calculations the DB is contracted to return.

## Exceptions and final verification

--allow-property-change excludes default-style checks for exact, justified properties; it does not create user authorization or necessity. Do not automatically exempt changed properties to remove warnings. Trying one convenient solution does not satisfy the criteria for an exception to a disfavored approach. Current explicit prohibitions still apply; general preferences follow the existing necessity criteria.

Also read style_exemptions and not_checked in results. Passing with warnings excluded does not establish verification of those properties. Do not add a procedure requiring approval documents, exception JSON, or checkpoint files every time.

Determine completion using actual requested scenarios, selecting relevant cases among periodic queries on the same screen, main-key changes, page transitions, resizing, empty results, and shutdown. A passing build does not establish display, binding, or query timing. Mark untested execution behavior as unverified.

Distinguish failures in validation-helper processes from business-app failures. Check actual exceptions, invocation, lifetime, and exit state; exclude that run from passing evidence. Distinguish scenarios verified after a fix from those still unexecuted. Do not make speculative business-source edits or hide execution results because helper code failed.
