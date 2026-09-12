# Handling actual secrets

Calling an already configured MCP or database does not itself justify reading secret configuration. Access only the necessary fields when credentials must actually be entered or settings changed; check presence, key names, and connection results instead of exposing values.

Do not print entire tables, Korean sentences, or connection strings containing passwords. `src.common.output.redact` is supplementary masking, not complete DLP. Do not copy secrets into documents, test fixtures, or memory. Prevent command-string interpolation from executing or exposing tokens.
