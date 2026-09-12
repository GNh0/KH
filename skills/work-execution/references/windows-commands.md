# Windows execution

Use the actual PowerShell/process environment and exact absolute paths. Move/delete files with native commands in one shell, verifying that targets are within the task's scope. Do not pass computed paths to another shell for deletion.

Start background helpers in hidden windows when the user does not need to see them. Preserve exit codes and stderr, and inspect actual outputs. Child-process PATH, bitness, and dependent DLLs may differ from the current shell. Minimize unchanged polling and full-log output.
