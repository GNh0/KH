from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict


READ_ONLY_ACTIONS = {
    "diff",
    "log",
    "rev-parse",
    "show",
    "status",
}
MUTATING_ACTIONS = {
    "add",
    "branch",
    "checkout",
    "cherry-pick",
    "clean",
    "commit",
    "fetch",
    "merge",
    "pull",
    "push",
    "rebase",
    "reset",
    "revert",
    "switch",
    "tag",
    "worktree",
}
BOOTSTRAP_ACTIONS = {"clone", "init"}
_ACTION_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")


@dataclass(frozen=True)
class GitWorkspaceProbe:
    project_path: str
    probe_start: str
    status: str
    is_git_backed: bool
    marker_path: str = ""
    marker_kind: str = ""
    git_dir: str = ""
    git_process_allowed: bool = False
    branch_finishing_applicable: bool = False
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def inspect_git_workspace(project: str | Path) -> GitWorkspaceProbe:
    """Inspect Git metadata without starting git.exe or another subprocess."""
    requested = Path(project).expanduser()
    try:
        requested = requested.resolve(strict=False)
    except OSError:
        requested = requested.absolute()

    probe_start = requested.parent if requested.exists() and requested.is_file() else requested
    current = probe_start
    while True:
        marker = current / ".git"
        try:
            if marker.is_dir():
                if _is_common_git_dir(marker):
                    return _git_backed_probe(
                        requested,
                        probe_start,
                        marker,
                        "directory",
                        marker,
                    )
                return _blocked_probe(
                    requested,
                    probe_start,
                    "invalid_git_marker",
                    marker,
                    ".git directory is missing required HEAD, objects, or refs metadata",
                )
            if marker.is_file():
                return _inspect_git_file(requested, probe_start, marker)
            if marker.exists():
                return _blocked_probe(
                    requested,
                    probe_start,
                    "invalid_git_marker",
                    marker,
                    "unsupported .git marker type",
                )
        except OSError as exc:
            return _blocked_probe(
                requested,
                probe_start,
                "git_marker_unreadable",
                marker,
                f"could not inspect .git marker: {exc}",
            )

        parent = current.parent
        if parent == current:
            break
        current = parent

    return GitWorkspaceProbe(
        project_path=str(requested),
        probe_start=str(probe_start),
        status="not_git_backed",
        is_git_backed=False,
        git_process_allowed=False,
        branch_finishing_applicable=False,
        reason="no .git directory or valid worktree .git file was found in the target ancestry",
    )


def authorize_git_action(
    project: str | Path,
    action: str,
    *,
    mutation_authorized: bool = False,
) -> Dict[str, Any]:
    probe = inspect_git_workspace(project)
    normalized = str(action or "").strip().lower()
    action_kind = _action_kind(normalized)

    if action_kind == "invalid":
        allowed = False
        requires_confirmation = False
        reason = "unknown or malformed Git action"
    elif action_kind == "bootstrap":
        allowed = bool(mutation_authorized)
        requires_confirmation = not allowed
        reason = (
            "explicit bootstrap authorization recorded"
            if allowed
            else "git init/clone requires explicit user or project authorization"
        )
    elif not probe.git_process_allowed:
        allowed = False
        requires_confirmation = False
        reason = "Git command blocked because the target is not a verified Git workspace"
    elif action_kind == "mutation" and not mutation_authorized:
        allowed = False
        requires_confirmation = True
        reason = "mutating Git action requires explicit user or project authorization"
    else:
        allowed = True
        requires_confirmation = False
        reason = "verified Git workspace permits this action"

    return {
        "action": normalized,
        "action_kind": action_kind,
        "allowed": allowed,
        "verdict": "allow" if allowed else ("ask" if requires_confirmation else "deny"),
        "requires_confirmation": requires_confirmation,
        "reason": reason,
        "probe": probe.to_dict(),
    }


def authorize_git_argv(
    project: str | Path,
    argv: list[str],
    *,
    mutation_authorized: bool = False,
) -> Dict[str, Any] | None:
    """Authorize a structured Git argv immediately before process creation."""
    if not argv:
        return None
    if _is_shell_wrapper(argv[0]):
        payload = " ".join(str(token) for token in argv[1:])
        if _contains_git_executable_text(payload):
            decision = authorize_git_action(project, "unparsed")
            return {
                **decision,
                "effective_project": str(Path(project).resolve(strict=False)),
                "target_source": "wrapped_git_command",
                "argv_mode": "structured",
                "reason": "wrapped Git execution is blocked; use direct structured Git argv",
            }
        return None
    if not _is_git_executable(argv[0]):
        return None
    effective_project = Path(project).expanduser()
    index = 1
    action = "unparsed"
    target_source = "cwd"
    while index < len(argv):
        token = str(argv[index])
        lowered = token.lower()
        if token == "-C":
            if index + 1 >= len(argv):
                break
            raw_target = str(argv[index + 1])
            candidate = Path(raw_target).expanduser()
            effective_project = (
                candidate
                if candidate.is_absolute()
                else effective_project / candidate
            )
            target_source = "git_-C"
            index += 2
            continue
        if token.startswith("-C") and len(token) > 2:
            raw_target = token[2:]
            candidate = Path(raw_target).expanduser()
            effective_project = (
                candidate
                if candidate.is_absolute()
                else effective_project / candidate
            )
            target_source = "git_-C"
            index += 1
            continue
        if lowered == "-c":
            index += 2
            continue
        if lowered.startswith("--git-dir") or lowered.startswith("--work-tree"):
            target_source = "unsupported_explicit_git_path"
            break
        if lowered in {
            "--bare",
            "--no-pager",
            "--paginate",
            "--literal-pathspecs",
            "--no-literal-pathspecs",
            "--glob-pathspecs",
            "--noglob-pathspecs",
            "--icase-pathspecs",
            "--no-replace-objects",
        }:
            index += 1
            continue
        if token.startswith("-"):
            break
        action = lowered
        break

    try:
        effective_project = effective_project.resolve(strict=False)
    except OSError:
        effective_project = effective_project.absolute()
    decision = authorize_git_action(
        effective_project,
        action,
        mutation_authorized=mutation_authorized,
    )
    return {
        **decision,
        "effective_project": str(effective_project),
        "target_source": target_source,
        "argv_mode": "structured",
    }


def _is_git_executable(executable: str) -> bool:
    return Path(str(executable).strip('"\'')).name.lower() in {"git", "git.exe"}


def _is_shell_wrapper(executable: str) -> bool:
    return Path(str(executable).strip('"\'')).name.lower() in {
        "cmd",
        "cmd.exe",
        "powershell",
        "powershell.exe",
        "pwsh",
        "pwsh.exe",
    }


def _contains_git_executable_text(payload: str) -> bool:
    return bool(
        re.search(
            r'''(?ix)(?:^|[\s;&|("'])(?:git(?:\.exe)?|[^\s"']*[\\/]git(?:\.exe)?)(?=[\s;&|)"']|$)''',
            payload or "",
        )
    )


def _inspect_git_file(
    requested: Path,
    probe_start: Path,
    marker: Path,
) -> GitWorkspaceProbe:
    try:
        content = marker.read_text(encoding="utf-8-sig").strip()
    except (OSError, UnicodeError) as exc:
        return _blocked_probe(
            requested,
            probe_start,
            "git_marker_unreadable",
            marker,
            f"could not read worktree .git file: {exc}",
        )

    first_line = content.splitlines()[0].strip() if content else ""
    prefix, separator, raw_target = first_line.partition(":")
    if separator != ":" or prefix.strip().lower() != "gitdir" or not raw_target.strip():
        return _blocked_probe(
            requested,
            probe_start,
            "invalid_git_marker",
            marker,
            "worktree .git file does not contain a gitdir pointer",
        )

    git_dir = Path(raw_target.strip()).expanduser()
    if not git_dir.is_absolute():
        git_dir = marker.parent / git_dir
    try:
        git_dir = git_dir.resolve(strict=False)
    except OSError:
        git_dir = git_dir.absolute()
    if not git_dir.is_dir():
        return _blocked_probe(
            requested,
            probe_start,
            "invalid_git_marker",
            marker,
            "worktree gitdir target does not exist as a directory",
        )
    if not _is_valid_gitdir_target(git_dir):
        return _blocked_probe(
            requested,
            probe_start,
            "invalid_git_marker",
            marker,
            "worktree gitdir target is missing required Git metadata",
        )
    return _git_backed_probe(requested, probe_start, marker, "worktree-file", git_dir)


def _is_valid_gitdir_target(git_dir: Path) -> bool:
    if _is_common_git_dir(git_dir):
        return True
    head = git_dir / "HEAD"
    commondir_file = git_dir / "commondir"
    if not _is_valid_head_file(head) or not commondir_file.is_file():
        return False
    try:
        raw_common = commondir_file.read_text(encoding="utf-8-sig").strip()
    except (OSError, UnicodeError):
        return False
    if not raw_common:
        return False
    common = Path(raw_common).expanduser()
    if not common.is_absolute():
        common = git_dir / common
    try:
        common = common.resolve(strict=False)
    except OSError:
        common = common.absolute()
    return _is_common_git_dir(common)


def _is_common_git_dir(git_dir: Path) -> bool:
    return (
        _is_valid_head_file(git_dir / "HEAD")
        and (git_dir / "objects").is_dir()
        and (git_dir / "refs").is_dir()
    )


def _is_valid_head_file(head: Path) -> bool:
    if not head.is_file():
        return False
    try:
        value = head.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        return False
    if re.fullmatch(r"ref:\s+refs/[A-Za-z0-9._/-]+", value):
        return ".." not in value and "//" not in value
    return bool(re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", value))


def _git_backed_probe(
    requested: Path,
    probe_start: Path,
    marker: Path,
    marker_kind: str,
    git_dir: Path,
) -> GitWorkspaceProbe:
    return GitWorkspaceProbe(
        project_path=str(requested),
        probe_start=str(probe_start),
        status="git_backed",
        is_git_backed=True,
        marker_path=str(marker),
        marker_kind=marker_kind,
        git_dir=str(git_dir),
        git_process_allowed=True,
        branch_finishing_applicable=True,
        reason="verified Git metadata with a filesystem-only probe",
    )


def _blocked_probe(
    requested: Path,
    probe_start: Path,
    status: str,
    marker: Path,
    reason: str,
) -> GitWorkspaceProbe:
    return GitWorkspaceProbe(
        project_path=str(requested),
        probe_start=str(probe_start),
        status=status,
        is_git_backed=False,
        marker_path=str(marker),
        git_process_allowed=False,
        branch_finishing_applicable=False,
        reason=reason,
    )


def _action_kind(action: str) -> str:
    if not _ACTION_PATTERN.fullmatch(action):
        return "invalid"
    if action in READ_ONLY_ACTIONS:
        return "read"
    if action in MUTATING_ACTIONS:
        return "mutation"
    if action in BOOTSTRAP_ACTIONS:
        return "bootstrap"
    return "invalid"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Probe Git workspace metadata without starting a Git process."
    )
    parser.add_argument("--project", default=".")
    parser.add_argument("--action", default="")
    parser.add_argument("--authorize-mutation", action="store_true")
    args = parser.parse_args(argv)

    if args.action:
        payload = authorize_git_action(
            args.project,
            args.action,
            mutation_authorized=args.authorize_mutation,
        )
        exit_code = 0 if payload["allowed"] else 3
    else:
        payload = inspect_git_workspace(args.project).to_dict()
        exit_code = 0
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
