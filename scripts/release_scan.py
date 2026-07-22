"""Release artifact hashing, native-binary checks, and leak scanning."""

from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path, PurePosixPath

_SECRET_NAME = re.compile(
    r"(^|[._-])(api[_-]?key|token|password|secret|private[_-]?key)([._-]|$)", re.I
)
_SECRET_VALUE = re.compile(
    r"Bearer\s+\S{12,}|hf_[A-Za-z0-9_=-]{8,}|(?:api[_-]?key|token|password|secret)\s*[:=]\s*['\"]?\S{8,}",
    re.I,
)
# Windows drive paths are matched case-insensitively (the drive letter and folder
# casing vary on a case-insensitive filesystem). POSIX home paths use canonical
# casing and must sit at a non-word boundary, so public URLs that merely contain a
# "/Home/" or "/home/" segment (e.g. a project homepage in a bundled license file)
# are not mistaken for a local user path. See app.diagnostics_privacy.POSIX_HOME_RE.
_LOCAL_PATH = re.compile(
    r"(?i:[A-Za-z]:\\+(?:Users|home)\\+)[^\r\n\"']+"
    r"|(?<![A-Za-z0-9_])/(?:home|Users)/[^\r\n\"']+"
)
_FORBIDDEN_NAMES = {".env", ".env.local", ".env.production", "desktop-instance.json"}
_FORBIDDEN_SUFFIXES = {".pfx", ".p12", ".pem", ".key", ".crt", ".cer"}
_FORBIDDEN_DIRS = {"models", "model-cache", "huggingface", "openvino-cache", ".cache", "cache"}
_TEXT_SUFFIXES = {
    ".txt",
    ".json",
    ".md",
    ".toml",
    ".ini",
    ".cfg",
    ".yaml",
    ".yml",
    ".ps1",
    ".py",
    ".iss",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_release_requirements(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError(f"Pinned release requirements are missing: {path}")
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        requirement = line.split(";", 1)[0].strip()
        if "==" not in requirement or any(
            op in requirement for op in (">=", "<=", "~=", "!=", " @ ")
        ):
            raise RuntimeError(
                f"Release dependency must use an exact == pin at {path.name}:{number}: {line}"
            )


def verify_native_distribution(root: Path) -> None:
    if not (root / "OpenVINOWindowsLLM.exe").is_file():
        raise RuntimeError("Packaged launcher executable is missing.")
    names = {item.name.lower() for item in root.rglob("*.dll")}
    required = {
        "OpenVINO runtime": "openvino.dll",
        "CPU plugin": "openvino_intel_cpu_plugin.dll",
        "GPU plugin": "openvino_intel_gpu_plugin.dll",
        "NPU plugin": "openvino_intel_npu_plugin.dll",
    }
    missing = [label for label, filename in required.items() if filename not in names]
    if missing:
        raise RuntimeError("Packaged native components are missing: " + ", ".join(missing))


def _check_name(relative: Path, suffix: str) -> None:
    dirs = {part.lower() for part in relative.parts[:-1]}
    name = relative.name.lower()
    if name in _FORBIDDEN_NAMES or suffix in _FORBIDDEN_SUFFIXES:
        raise RuntimeError(f"Forbidden release file: {relative.as_posix()}")
    if dirs & _FORBIDDEN_DIRS:
        raise RuntimeError(f"Model or cache directory included in release: {relative.as_posix()}")
    if _SECRET_NAME.search(name):
        raise RuntimeError(f"Secret-like filename included in release: {relative.as_posix()}")


def _check_text(text: str, relative: Path) -> None:
    if _SECRET_VALUE.search(text):
        raise RuntimeError(f"Secret-like value found in release text: {relative.as_posix()}")
    if _LOCAL_PATH.search(text):
        raise RuntimeError(f"Local user path found in release text: {relative.as_posix()}")


def _scan_file(path: Path, relative: Path) -> None:
    suffix = path.suffix.lower()
    _check_name(relative, suffix)
    if suffix in _TEXT_SUFFIXES and path.stat().st_size <= 2 * 1024 * 1024:
        _check_text(path.read_text(encoding="utf-8", errors="ignore"), relative)


def scan_release_path(path: Path) -> None:
    if path.is_dir():
        for item in path.rglob("*"):
            if item.is_symlink():
                raise RuntimeError(f"Symlink is not allowed in release output: {item}")
            if item.is_file():
                _scan_file(item, item.relative_to(path))
        return
    if path.suffix.lower() != ".zip":
        _scan_file(path, Path(path.name))
        return
    with zipfile.ZipFile(path) as archive:
        for item in archive.infolist():
            pure = PurePosixPath(item.filename.replace("\\", "/"))
            if pure.is_absolute() or ".." in pure.parts or not pure.parts:
                raise RuntimeError(f"Unsafe archive path: {item.filename}")
            if ((item.external_attr >> 16) & 0o170000) == 0o120000:
                raise RuntimeError(f"Symlink is not allowed in release archive: {item.filename}")
            if item.is_dir():
                continue
            relative = Path(*pure.parts)
            suffix = relative.suffix.lower()
            try:
                _check_name(relative, suffix)
            except RuntimeError as exc:
                message = str(exc).replace(
                    "Forbidden release file", "Forbidden release archive entry"
                )
                raise RuntimeError(message) from exc
            if suffix in _TEXT_SUFFIXES and item.file_size <= 2 * 1024 * 1024:
                _check_text(archive.read(item).decode("utf-8", errors="ignore"), relative)


def write_checksums(output_dir: Path, version: str, filename_factory) -> Path:
    checksum_path = output_dir / filename_factory(version, "checksums")
    files = sorted(
        path for path in output_dir.iterdir() if path.is_file() and path != checksum_path
    )
    if not files:
        raise RuntimeError("No release artifacts were found for checksum generation.")
    checksum_path.write_text(
        "\n".join(f"{sha256_file(path)}  {path.name}" for path in files) + "\n", encoding="ascii"
    )
    verify_checksums(checksum_path)
    return checksum_path


def verify_checksums(checksum_path: Path) -> None:
    for line in checksum_path.read_text(encoding="ascii").splitlines():
        digest, separator, filename = line.partition("  ")
        if not separator or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise RuntimeError(f"Malformed checksum line: {line}")
        target = checksum_path.parent / filename
        if not target.is_file() or sha256_file(target) != digest:
            raise RuntimeError(f"Checksum verification failed for {filename}")
