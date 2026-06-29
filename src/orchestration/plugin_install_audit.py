from __future__ import annotations

import argparse
import json
import os
import re
try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    tomllib = None  # type: ignore[assignment]
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass(frozen=True)
class MarketplaceConfig:
    path: str
    exists: bool
    source: str = ""
    ref: str = ""
    sparse_paths: List[str] = field(default_factory=list)
    last_revision: str = ""
    parse_status: str = "not_checked"
    parse_error: str = ""
    encoding_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MarketplacePluginSource:
    descriptor_path: str
    exists: bool
    plugin_name: str = ""
    source_url: str = ""
    source_ref: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class InstalledPluginCache:
    root: str
    version_dir: str
    plugin_version: str = ""
    codex_plugin_version: str = ""
    skill_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class KhPluginInstallAudit:
    status: str
    codex_home: str
    repository_root: str
    marketplace_config: MarketplaceConfig
    marketplace_plugin_source: MarketplacePluginSource
    source_versions: Dict[str, str]
    installed_caches: List[InstalledPluginCache]
    latest_installed_version: str
    expected_source_version: str
    findings: List[str]
    recommended_actions: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "codex_home": self.codex_home,
            "repository_root": self.repository_root,
            "marketplace_config": self.marketplace_config.to_dict(),
            "marketplace_plugin_source": self.marketplace_plugin_source.to_dict(),
            "source_versions": dict(self.source_versions),
            "installed_caches": [cache.to_dict() for cache in self.installed_caches],
            "latest_installed_version": self.latest_installed_version,
            "expected_source_version": self.expected_source_version,
            "findings": list(self.findings),
            "recommended_actions": list(self.recommended_actions),
        }

    def to_summary_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "marketplace_ref": self.marketplace_config.ref,
            "marketplace_last_revision": self.marketplace_config.last_revision,
            "plugin_source_ref": self.marketplace_plugin_source.source_ref,
            "expected_source_version": self.expected_source_version,
            "latest_installed_version": self.latest_installed_version,
            "installed_cache_versions": [cache.version_dir for cache in self.installed_caches],
            "config_parse_status": self.marketplace_config.parse_status,
            "config_encoding_warnings": list(self.marketplace_config.encoding_warnings),
            "findings": list(self.findings),
            "recommended_actions": list(self.recommended_actions),
        }


def audit_kh_plugin_install(
    codex_home: str | os.PathLike[str] | None = None,
    repository_root: str | os.PathLike[str] | None = None,
    marketplace_name: str = "kh-uaf-marketplace",
    plugin_name: str = "kh-uaf",
) -> KhPluginInstallAudit:
    codex_root = Path(codex_home or os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser().resolve()
    repo_root = Path(repository_root).expanduser().resolve() if repository_root else _repo_root()

    config = _read_marketplace_config(codex_root / "config.toml", marketplace_name)
    descriptor = _read_marketplace_plugin_source(repo_root / ".agents" / "plugins" / "marketplace.json", plugin_name)
    source_versions = _read_source_versions(repo_root)
    caches = _read_installed_caches(codex_root, marketplace_name, plugin_name)

    latest_installed = caches[0].plugin_version or caches[0].codex_plugin_version if caches else ""
    expected_source = source_versions.get("codex_plugin") or source_versions.get("root_plugin", "")
    findings: List[str] = []
    actions: List[str] = []

    if not config.exists:
        findings.append("Codex config.toml was not found.")
        actions.append("Add the KH UAF marketplace in Codex before testing plugin installation.")
    elif config.parse_status == "invalid":
        findings.append(f"Codex config.toml is not valid TOML: {config.parse_error}")
        actions.append("Fix config.toml parse errors before upgrading or judging plugin cache state.")
    elif config.encoding_warnings:
        findings.append("Codex config.toml contains possible encoding damage or replacement characters.")
        actions.append("Review config.toml encoding and repair damaged text before editing marketplace settings.")
    elif config.ref == "main" and descriptor.source_ref:
        findings.append(
            "Marketplace config ref is the marketplace descriptor layer; plugin source ref comes from marketplace.json."
        )
    elif config.ref and descriptor.source_ref and config.ref != descriptor.source_ref:
        findings.append(
            "Marketplace config ref differs from plugin source ref. This can be valid when main hosts the marketplace descriptor."
        )

    if not descriptor.exists:
        findings.append("Repository marketplace descriptor was not found.")
        actions.append("Check .agents/plugins/marketplace.json before publishing the marketplace.")
    elif descriptor.source_ref != "codex-runtime":
        findings.append(f"Plugin source ref is {descriptor.source_ref or '<empty>'}, expected codex-runtime.")
        actions.append("Set .agents/plugins/marketplace.json plugin source ref to codex-runtime if that is the intended runtime branch.")

    if not caches:
        findings.append("No installed KH UAF cache was found under Codex plugin cache.")
        actions.append("Install or upgrade the KH UAF marketplace plugin, then start a fresh session.")
    elif expected_source and latest_installed and _version_key(latest_installed) < _version_key(expected_source):
        findings.append(
            f"Installed KH UAF cache is behind source version: installed {latest_installed}, source {expected_source}."
        )
        actions.append("Upgrade KH UAF in Codex and open a fresh session before judging blind automatic intake.")
    elif expected_source and latest_installed:
        findings.append(f"Installed KH UAF cache version matches or exceeds source version: {latest_installed}.")

    if caches:
        actions.append("Verify the active session skill list points at the latest installed cache path, not only the filesystem cache.")

    status = "ok"
    if any(
        marker in finding
        for finding in findings
        for marker in [
            "behind source version",
            "No installed",
            "not found",
            "not valid TOML",
            "encoding damage",
            "replacement characters",
        ]
    ):
        status = "attention_required"

    return KhPluginInstallAudit(
        status=status,
        codex_home=str(codex_root),
        repository_root=str(repo_root),
        marketplace_config=config,
        marketplace_plugin_source=descriptor,
        source_versions=source_versions,
        installed_caches=caches,
        latest_installed_version=latest_installed,
        expected_source_version=expected_source,
        findings=findings,
        recommended_actions=actions,
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_marketplace_config(path: Path, marketplace_name: str) -> MarketplaceConfig:
    if not path.exists():
        return MarketplaceConfig(path=str(path), exists=False)

    text = path.read_text(encoding="utf-8", errors="replace")
    encoding_warnings = _config_encoding_warnings(text)
    parse_status = "unavailable"
    parse_error = ""
    parsed_data: Dict[str, Any] = {}
    if tomllib is not None:
        try:
            parsed = tomllib.loads(text)
            parse_status = "ok"
            marketplaces = parsed.get("marketplaces", {}) if isinstance(parsed, dict) else {}
            section = marketplaces.get(marketplace_name, {}) if isinstance(marketplaces, dict) else {}
            if isinstance(section, dict):
                parsed_data = dict(section)
        except Exception as exc:  # TOMLDecodeError keeps Python-version-specific type details
            parse_status = "invalid"
            parse_error = str(exc)

    block: List[str] = []
    in_block = False
    header = f"[marketplaces.{marketplace_name}]"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == header:
            in_block = True
            continue
        if in_block and stripped.startswith("[") and stripped.endswith("]"):
            break
        if in_block:
            block.append(stripped)

    fallback_data = _parse_simple_toml_block(block)
    data = {**fallback_data, **parsed_data}
    return MarketplaceConfig(
        path=str(path),
        exists=True,
        source=str(data.get("source", "")),
        ref=str(data.get("ref", "")),
        sparse_paths=list(data.get("sparse_paths", [])),
        last_revision=str(data.get("last_revision", "")),
        parse_status=parse_status,
        parse_error=parse_error,
        encoding_warnings=encoding_warnings,
    )


def _parse_simple_toml_block(lines: List[str]) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    for line in lines:
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw = line.split("=", 1)
        key = key.strip()
        raw = raw.strip()
        if raw.startswith("[") and raw.endswith("]"):
            items = []
            for part in raw[1:-1].split(","):
                value = part.strip().strip("\"'")
                if value:
                    items.append(value)
            data[key] = items
        else:
            data[key] = raw.strip("\"'")
    return data


def _config_encoding_warnings(text: str) -> List[str]:
    warnings: List[str] = []
    if "\ufffd" in text:
        warnings.append("unicode_replacement_character")
    return warnings


def _read_marketplace_plugin_source(path: Path, plugin_name: str) -> MarketplacePluginSource:
    if not path.exists():
        return MarketplacePluginSource(descriptor_path=str(path), exists=False)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return MarketplacePluginSource(descriptor_path=str(path), exists=True)
    for plugin in data.get("plugins", []):
        if plugin.get("name") != plugin_name:
            continue
        source = plugin.get("source", {}) or {}
        return MarketplacePluginSource(
            descriptor_path=str(path),
            exists=True,
            plugin_name=str(plugin.get("name", "")),
            source_url=str(source.get("url", "")),
            source_ref=str(source.get("ref", "")),
        )
    return MarketplacePluginSource(descriptor_path=str(path), exists=True)


def _read_source_versions(repo_root: Path) -> Dict[str, str]:
    return {
        "root_plugin": _read_json_version(repo_root / "plugin.json"),
        "codex_plugin": _read_json_version(repo_root / ".codex-plugin" / "plugin.json"),
    }


def _read_json_version(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get("version", ""))
    except json.JSONDecodeError:
        return ""


def _read_installed_caches(codex_home: Path, marketplace_name: str, plugin_name: str) -> List[InstalledPluginCache]:
    cache_root = codex_home / "plugins" / "cache" / marketplace_name / plugin_name
    if not cache_root.is_dir():
        return []
    caches: List[InstalledPluginCache] = []
    for child in cache_root.iterdir():
        if not child.is_dir():
            continue
        caches.append(
            InstalledPluginCache(
                root=str(child),
                version_dir=child.name,
                plugin_version=_read_json_version(child / "plugin.json"),
                codex_plugin_version=_read_json_version(child / ".codex-plugin" / "plugin.json"),
                skill_count=_count_skill_files(child / "skills"),
            )
        )
    return sorted(caches, key=lambda cache: _version_key(cache.plugin_version or cache.codex_plugin_version or cache.version_dir), reverse=True)


def _count_skill_files(skills_dir: Path) -> int:
    if not skills_dir.is_dir():
        return 0
    return sum(1 for path in skills_dir.iterdir() if (path / "SKILL.md").is_file())


def _version_key(value: str) -> tuple:
    parts = []
    for part in re.split(r"[^0-9]+", value):
        if part:
            parts.append(int(part))
    return tuple(parts or [0])


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit KH UAF Codex marketplace and installed plugin cache state.")
    parser.add_argument("--codex-home", default=None, help="Override Codex home directory.")
    parser.add_argument("--repo", default=None, help="Override KH repository root.")
    parser.add_argument("--summary", action="store_true", help="Print a compact summary.")
    parser.add_argument("--strict", action="store_true", help="Return a non-zero exit code when attention is required.")
    args = parser.parse_args(argv)

    audit = audit_kh_plugin_install(codex_home=args.codex_home, repository_root=args.repo)
    payload = audit.to_summary_dict() if args.summary else audit.to_dict()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if args.strict and audit.status != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
