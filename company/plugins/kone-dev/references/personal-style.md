# Personal style

Read only the style for the current work. Run `python -B <plugin-root>/scripts/kone_style.py show <topic>` with `sql`, `csharp`, `pb`, or `work`. The JSON contains the selected absolute path and its Markdown text. This command reads files and creates nothing. With Python unavailable, read the same file directly when its absolute path is known.

Read it when that topic first matters in the task and reuse the result. Reload when the selected location or style changes; do not rerun it for every small continuation.

The location is `KONE_DEV_STYLE_HOME`, otherwise `<CODEX_HOME>/kone-dev-style`, otherwise `~/.codex/kone-dev-style`. For existing installations, `COMPANY_DEV_STYLE_HOME` remains a fallback; when the new default folder is absent, an existing `company-dev-style` folder under the same home is reused. Do not move or overwrite existing employee files during an update. An unset or empty topic inherits approved project examples. Do not search colleague profiles or conversation history to discover preferences.

Use personal preferences for formatting and implementation choices left open by the current request and actual project contracts. They do not change data meaning, required APIs, company requirements, permissions, or execution authorization. Do not treat a preference as a universal ban. Follow the current user's explicit constraints; explain a necessary departure with its actual implementation reason.

Employees can specify preferred forms, concrete patterns to avoid, approved reference file/method locations and necessary exceptions in the same topic file. Keep any illustrative code fictional and separate from confidential business code. Actual project source remains the authority for behavior and APIs. Do not copy colleague profiles or edit the shared plugin to establish an individual preference.

`kone_check.py` validates its reported source/contract items without imposing the original author's style. It does not automatically enforce free-form personal style files. Review the final relevant text against the selected preferences and actual project examples.
