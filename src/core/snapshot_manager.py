import os
import json
import time
import gzip
import hashlib

from src.orchestration.runtime_paths import project_snapshot_dir

class SnapshotManager:
    """Project rollback and gzip snapshot store."""
    def __init__(self, base_dir: str, thread_id: str = ""):
        self.base_dir = os.path.abspath(base_dir)
        self.thread_id = thread_id
        self.snapshot_dir = str(project_snapshot_dir(self.base_dir, thread_id=thread_id))
        self.log_file = os.path.join(self.snapshot_dir, "commit_log.json")

    def _sanitize_path(self, file_name: str) -> str:
        """Validate paths against traversal outside the project root."""
        safe_path = os.path.abspath(os.path.join(self.base_dir, file_name))
        if os.path.commonpath([self.base_dir, safe_path]) != self.base_dir:
            raise PermissionError(f"[security] path escapes project root: {file_name}")
        return safe_path

    def _is_snapshot_path(self, file_path: str) -> bool:
        snapshot_root = os.path.abspath(self.snapshot_dir)
        target = os.path.abspath(file_path)
        try:
            if os.path.commonpath([snapshot_root, target]) == snapshot_root:
                return True
        except ValueError:
            pass
        relative_path = os.path.relpath(target, self.base_dir)
        return any(part == ".snapshots" for part in relative_path.split(os.sep))

    def _ensure_store(self) -> None:
        os.makedirs(self.snapshot_dir, exist_ok=True)
        if not os.path.exists(self.log_file):
            with open(self.log_file, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _read_logs(self) -> list:
        if not os.path.exists(self.log_file):
            return []
        with open(self.log_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_logs(self, logs: list) -> None:
        self._ensure_store()
        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=4)

    def commit(self, file_name: str, code: str, message: str) -> str:
        """Backup current code into a timestamped gzip snapshot."""
        safe_path = self._sanitize_path(file_name)
        
        if self._is_snapshot_path(safe_path):
            raise PermissionError(f"[snapshot] protected snapshot metadata path: {file_name}")
            
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_basename = os.path.basename(file_name)
        digest = hashlib.sha256(
            f"{safe_basename}\0{message}\0{time.time_ns()}".encode("utf-8")
        ).hexdigest()[:8]
        version_id = f"{safe_basename}_{timestamp}_{digest}.gz"
        backup_path = os.path.join(self.snapshot_dir, version_id)
        self._ensure_store()
        
        with gzip.open(backup_path, 'wt', encoding='utf-8') as f:
            f.write(code)
            
        logs = self._read_logs()
            
        logs.append({
            "version_id": version_id,
            "kind": "file",
            "file": file_name,
            "message": message,
            "timestamp": timestamp
        })
        
        self._write_logs(logs)
            
        print(f"[Snapshot] file snapshot created: {file_name} -> {version_id}")
        return version_id

    def commit_many(self, file_names: list, message: str) -> str:
        """Create one work-level snapshot bundle for multiple project files."""
        if not file_names:
            raise ValueError("commit_many requires at least one file")

        entries = []
        seen = set()
        for file_name in file_names:
            if file_name in seen:
                continue
            seen.add(file_name)
            safe_path = self._sanitize_path(file_name)
            if self._is_snapshot_path(safe_path):
                raise PermissionError(f"[snapshot] protected snapshot metadata path: {file_name}")
            exists = os.path.exists(safe_path)
            content = ""
            if exists:
                with open(safe_path, "r", encoding="utf-8") as handle:
                    content = handle.read()
            entries.append({
                "file": file_name,
                "exists": exists,
                "content": content,
            })

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        digest = hashlib.sha256(
            json.dumps(
                {"files": [entry["file"] for entry in entries], "message": message},
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:8]
        version_id = f"work_snapshot_{timestamp}_{digest}.json.gz"
        backup_path = os.path.join(self.snapshot_dir, version_id)
        self._ensure_store()
        with gzip.open(backup_path, "wt", encoding="utf-8") as handle:
            json.dump(
                {
                    "version_id": version_id,
                    "message": message,
                    "timestamp": timestamp,
                    "files": entries,
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )

        logs = self._read_logs()
        logs.append({
            "version_id": version_id,
            "kind": "bundle",
            "files": [entry["file"] for entry in entries],
            "message": message,
            "timestamp": timestamp,
        })
        self._write_logs(logs)
        print(f"[Snapshot] work snapshot completed: {version_id}")
        return version_id

    def rollback(self, target_version_id: str) -> bool:
        """Restore a project file or work snapshot by version id."""
        return self.rollback_result(target_version_id)["status"] == "restored"

    def rollback_result(self, target_version_id: str) -> dict:
        """Restore a project file or work snapshot and return a structured summary."""
        logs = self._read_logs()
            
        target_entry = None
        for entry in logs:
            if entry["version_id"] == target_version_id:
                target_entry = entry
                break
                
        if not target_entry:
            print(f"[Snapshot] version id not found: {target_version_id}")
            return {
                "status": "missing",
                "version_id": target_version_id,
                "restored_files": [],
                "removed_files": [],
                "failed_files": [],
                "message": "version id not found",
            }
            
        if target_entry.get("kind") == "bundle":
            return self._rollback_bundle_result(target_version_id)

        target_file = target_entry["file"]
        restore_path = self._sanitize_path(target_file)
        
        if self._is_snapshot_path(restore_path):
            raise PermissionError(f"[snapshot] protected snapshot metadata path: {target_file}")
        
        backup_path = os.path.join(self.snapshot_dir, target_version_id)
        if not os.path.exists(backup_path):
            print(f"[Snapshot] missing snapshot file: {backup_path}")
            return {
                "status": "missing",
                "version_id": target_version_id,
                "restored_files": [],
                "removed_files": [],
                "failed_files": [target_file],
                "message": "snapshot file missing",
            }
            
        os.makedirs(os.path.dirname(restore_path), exist_ok=True)
        
        with gzip.open(backup_path, 'rt', encoding='utf-8') as src:
            restored_code = src.read()
            with open(restore_path, "w", encoding="utf-8") as dst:
                dst.write(restored_code)
            
        print(f"[Snapshot] file snapshot restored: {target_file} <- {target_version_id}")
        return {
            "status": "restored",
            "version_id": target_version_id,
            "restored_files": [target_file],
            "removed_files": [],
            "failed_files": [],
            "message": "file snapshot restored",
        }

    def _rollback_bundle(self, target_version_id: str) -> bool:
        return self._rollback_bundle_result(target_version_id)["status"] == "restored"

    def _rollback_bundle_result(self, target_version_id: str) -> dict:
        backup_path = os.path.join(self.snapshot_dir, target_version_id)
        if not os.path.exists(backup_path):
            print(f"[Snapshot] missing snapshot bundle: {backup_path}")
            return {
                "status": "missing",
                "version_id": target_version_id,
                "restored_files": [],
                "removed_files": [],
                "failed_files": [],
                "message": "snapshot bundle missing",
            }

        with gzip.open(backup_path, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)

        restored = []
        removed = []
        failed = []
        for entry in payload.get("files", []):
            file_name = entry.get("file", "")
            try:
                restore_path = self._sanitize_path(file_name)
                if self._is_snapshot_path(restore_path):
                    raise PermissionError(f"[snapshot] protected snapshot metadata path: {file_name}")
                if not entry.get("exists", False):
                    if os.path.exists(restore_path):
                        os.remove(restore_path)
                        removed.append(file_name)
                    continue
                os.makedirs(os.path.dirname(restore_path), exist_ok=True)
                with open(restore_path, "w", encoding="utf-8") as handle:
                    handle.write(entry.get("content", ""))
                restored.append(file_name)
            except Exception as exc:
                failed.append({
                    "file": file_name,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                })

        print(f"[Snapshot] work snapshot restored: {target_version_id}")
        return {
            "status": "restored" if not failed else "partial",
            "version_id": target_version_id,
            "restored_files": restored,
            "removed_files": removed,
            "failed_files": failed,
            "message": "work snapshot restored" if not failed else "work snapshot partially restored",
        }

    def prune(self, max_snapshots: int) -> dict:
        """Keep the newest snapshot log entries and delete older snapshot files."""
        if max_snapshots < 0:
            raise ValueError("max_snapshots must be >= 0")

        logs = self._read_logs()
        kept_logs = logs[-max_snapshots:] if max_snapshots else []
        removed_logs = logs[: len(logs) - len(kept_logs)]
        deleted = []

        snapshot_root = os.path.abspath(self.snapshot_dir)
        for entry in removed_logs:
            version_id = entry.get("version_id", "")
            if not version_id:
                continue
            snapshot_path = os.path.abspath(os.path.join(self.snapshot_dir, version_id))
            try:
                if os.path.commonpath([snapshot_root, snapshot_path]) != snapshot_root:
                    continue
            except ValueError:
                continue
            if os.path.exists(snapshot_path):
                os.remove(snapshot_path)
            deleted.append(version_id)

        self._write_logs(kept_logs)
        return {
            "before": len(logs),
            "after": len(kept_logs),
            "kept": [entry.get("version_id", "") for entry in kept_logs],
            "deleted": deleted,
        }
