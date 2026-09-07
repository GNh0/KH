"""Exact input paths and optimistic conflict detection, without automatic backups."""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import tempfile


@dataclass(frozen=True)
class FileInput:
    path: Path
    data: bytes
    sha256: str

    def text(self, encoding: str = "utf-8-sig") -> str:
        return self.data.decode(encoding, errors="strict")


def read_file(path: str | Path, *, max_bytes: int | None = None) -> FileInput:
    requested = Path(path)
    if not requested.is_absolute():
        raise ValueError("input path must be absolute")
    resolved = requested.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError("input must be a regular file")
    with resolved.open("rb") as stream:
        before = os.fstat(stream.fileno())
        if max_bytes is not None and before.st_size > max_bytes:
            raise ValueError("input exceeds the selected read limit")
        data = stream.read() if max_bytes is None else stream.read(max_bytes + 1)
        after = os.fstat(stream.fileno())
    if max_bytes is not None and len(data) > max_bytes:
        raise ValueError("input grew beyond the selected read limit")
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError("input changed while reading; read the current file again")
    return FileInput(resolved, data, hashlib.sha256(data).hexdigest())


def verify_unchanged(snapshot: FileInput) -> None:
    if read_file(snapshot.path).sha256 != snapshot.sha256:
        raise RuntimeError(f"input changed since inspection: {snapshot.path}")


def write_output(path: str | Path, data: bytes, *, expected_sha256: str | None = None) -> Path:
    """Write an explicitly requested output; existing files require a matching hash.

    The final hash check detects ordinary intervening edits, not an OS-wide lock.
    Host coordination is still needed for concurrent writers.
    """
    destination = Path(path)
    if not destination.is_absolute():
        raise ValueError("output path must be absolute")
    destination = destination.resolve()
    if destination.exists():
        if expected_sha256 is None or read_file(destination).sha256 != expected_sha256:
            raise FileExistsError("existing output needs its current SHA-256 for replacement")
    elif expected_sha256 is not None:
        raise FileNotFoundError("expected output no longer exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".kh-output-", dir=destination.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
        if destination.exists():
            if expected_sha256 is None or read_file(destination).sha256 != expected_sha256:
                raise RuntimeError("output changed before replacement")
        elif expected_sha256 is not None:
            raise FileNotFoundError("expected output disappeared before replacement")
        if expected_sha256 is None:
            # Linking in the same directory fails atomically if another writer
            # created the destination. Never replace that writer's new file.
            os.link(temporary, destination)
        else:
            os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return destination
