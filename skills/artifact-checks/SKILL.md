---
name: artifact-checks
description: Check requested deliverables for content, file structure, and readable rendered output when several formats or a separate artifact audit are involved.
---

# Artifact checks

Compare final deliverables with the user's requested formats, locations, and content. Use the currently available dedicated skills/tools to create and render documents, spreadsheets, slides, and PDFs.

For file-structure checks alone, optionally run `python <plugin-root>/scripts/kh_check.py artifact <absolute-file>`. ZIP/XML/header checks do not establish content correctness or successful rendering. If no renderer is available, report that only structure was checked.

Inspect the actual format-specific results: tables, formulas, groups, report H/D/F bands, pages, and Korean text readability. Create a requirements mapping only when useful; do not require a fixed outline or multiple separate status files.
