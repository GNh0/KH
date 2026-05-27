import os
import json
import time
import gzip

class SnapshotManager:
    """
    [V2.3] 프로젝트 상태 롤백 및 백업 시스템 (GZIP 압축 최적화 적용)
    """
    def __init__(self, base_dir: str):
        self.base_dir = os.path.abspath(base_dir)
        self.snapshot_dir = os.path.join(self.base_dir, ".snapshots")
        self.log_file = os.path.join(self.snapshot_dir, "commit_log.json")
        
        if not os.path.exists(self.snapshot_dir):
            os.makedirs(self.snapshot_dir)
            
        if not os.path.exists(self.log_file):
            with open(self.log_file, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _sanitize_path(self, file_name: str) -> str:
        """[V2.1 보안] Path Traversal 공격 방어를 위한 경로 검증"""
        safe_path = os.path.abspath(os.path.join(self.base_dir, file_name))
        if os.path.commonpath([self.base_dir, safe_path]) != self.base_dir:
            raise PermissionError(f"[보안 위반] 프로젝트 디렉토리를 벗어나는 경로는 접근할 수 없습니다: {file_name}")
        return safe_path

    def _is_snapshot_path(self, file_path: str) -> bool:
        return os.path.commonpath([self.snapshot_dir, file_path]) == self.snapshot_dir

    def commit(self, file_name: str, code: str, message: str) -> str:
        """파일의 현재 코드를 시간 기반 스냅샷으로 백업합니다."""
        safe_path = self._sanitize_path(file_name)
        
        # [V2.1 보안] 메타데이터 조작 시도 원천 차단
        if self._is_snapshot_path(safe_path):
            raise PermissionError(f"[보안 위반] 스냅샷 보호 구역(.snapshots) 내의 파일은 조작할 수 없습니다: {file_name}")
            
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_basename = os.path.basename(file_name)
        # [V2.3] .gz 확장자로 저장
        version_id = f"{safe_basename}_{timestamp}.gz"
        backup_path = os.path.join(self.snapshot_dir, version_id)
        
        # [V2.3] 디스크 용량 절약을 위한 GZIP 압축 저장
        with gzip.open(backup_path, 'wt', encoding='utf-8') as f:
            f.write(code)
            
        with open(self.log_file, "r", encoding="utf-8") as f:
            logs = json.load(f)
            
        logs.append({
            "version_id": version_id,
            "file": file_name,
            "message": message,
            "timestamp": timestamp
        })
        
        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=4)
            
        print(f"[Snapshot] '{file_name}' 백업 완료 (압축됨: {version_id})")
        return version_id

    def rollback(self, target_version_id: str) -> bool:
        """특정 버전 ID로 프로젝트 파일을 롤백(복원)합니다."""
        with open(self.log_file, "r", encoding="utf-8") as f:
            logs = json.load(f)
            
        target_entry = None
        for entry in logs:
            if entry["version_id"] == target_version_id:
                target_entry = entry
                break
                
        if not target_entry:
            print(f"❌ [Snapshot] 버전 ID '{target_version_id}'를 찾을 수 없습니다.")
            return False
            
        target_file = target_entry["file"]
        restore_path = self._sanitize_path(target_file)
        
        if self._is_snapshot_path(restore_path):
            raise PermissionError(f"[보안 위반] 보호 구역 내 파일 덮어쓰기 시도 감지됨: {target_file}")
        
        backup_path = os.path.join(self.snapshot_dir, target_version_id)
        if not os.path.exists(backup_path):
            print(f"❌ [Snapshot] 백업 파일이 유실되었습니다: {backup_path}")
            return False
            
        os.makedirs(os.path.dirname(restore_path), exist_ok=True)
        
        # [V2.3] GZIP 무손실 압축 해제 및 복원
        with gzip.open(backup_path, 'rt', encoding='utf-8') as src:
            restored_code = src.read()
            with open(restore_path, "w", encoding="utf-8") as dst:
                dst.write(restored_code)
            
        print(f"✅ [Snapshot] '{target_file}' 파일이 '{target_version_id}' 버전으로 복구되었습니다.")
        return True
