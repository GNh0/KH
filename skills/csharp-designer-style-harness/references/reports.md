# Reports, previews and printing

Read this for creating or changing report definitions, report previews or print actions. Screen layout and printed-document layout are separate contracts even when they share data.

## Establish the actual report path

Read an approved comparable report's code, Designer/resource, base class, relevant control implementations and caller/print helper. Use the user's named comparison for style; verify every reused API and assembly in the actual target project. Inspect complete relevant construction and binding blocks, not only class names or references to them.

Compare the component roles and ownership before writing. For example, if comparable detail rows use project XRTable rows/cells, follow that construction for the equivalent tabular region rather than replacing it with individually positioned labels. Labels remain appropriate for roles such as free text/headings when supported by the selected design. Select controls from their output role and the actual report pattern.

Map the requested data/result sets, keys, ordering, grouping, totals, chart series and empty-result behavior to the report bindings. A screen ChartControl and an embedded report chart are different output paths; choose from the requested behavior and available target APIs. Do not substitute one and claim reproduction of the other without checking the final output.

## Place behavior at its verified owner

Follow the target's division between serializable Designer layout, code-behind data/behavior and the screen's query/print actions. Preserve working report/helper initialization; add only the missing behavior or dependency established by the request and actual path. Do not use an ad hoc generator or compile wrapper as the final product.

Resolve page size/orientation, margins, data width, chart/detail order and repetition from the latest request plus the approved report. Check whether a chart should flow after detail, appear on every page or occupy a fixed page area; these require different band/flow choices. Check page-by-page approval/signature/header repetition independently. Do not inherit an earlier placement after the user corrects it.

For a combined data/chart document, verify that the preview and print command reach that report with the intended query results. A successful query or report allocation does not establish a visible preview. Preview zoom, scrollbars and screen docking should follow the actual preview host/request, rather than compensating for an incorrect printable layout.

## Integrate and verify the actual deliverable

Write the requested code, Designer and resource to their final target paths. Inspect the actual project registrations, DependentUpon/resource relationships and required references/HintPaths. Infer required assemblies from the target APIs and working project references, not from namespaces alone. A temporary compile supplied with extra DLLs does not prove that the real project or Visual Studio Designer can load the result. A generic Designer error near a constructor may be a missing dependency; diagnose the actual exception before inventing a method/layout restriction.

Optional static check: pass `--project-file <actual.csproj>` to the C# or Designer checker. Its supplied source/companion files are checked automatically; add `--project-item <actual.resx>` for a selected resource and `--required-reference <verified-assembly-name>` for each required direct assembly. The check reads project XML only. Conditional/generated/SDK items can remain unverified; direct registration is not compilation, resource binding, assembly loading or a live Designer test.

Compare the final report construction and changed caller bodies with the selected source. Then verify the requested preview/print scenarios at the level available: actual project build when permitted, Designer load and rendered output where available, representative multi-page/empty data when relevant. Preserve user restrictions on builds and DB execution. Report exactly which levels were checked and which remain unverified; do not turn unavailable UI/runtime evidence into a passing claim.
