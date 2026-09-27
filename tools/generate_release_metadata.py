from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from codex_usage_monitor.release_metadata import release_metadata, version_tuple  # noqa: E402


def main() -> int:
    metadata = release_metadata()
    build_dir = ROOT / "build"
    installer_dir = ROOT / "installer"
    build_dir.mkdir(parents=True, exist_ok=True)
    installer_dir.mkdir(parents=True, exist_ok=True)

    version_info_path = build_dir / "version_info.txt"
    installer_version_path = installer_dir / "version.iss"

    file_version = version_tuple()
    version_info_path.write_text(
        _version_info_text(metadata, file_version),
        encoding="utf-8",
    )
    installer_version_path.write_text(
        _installer_version_text(metadata),
        encoding="utf-8",
    )
    print(f"Wrote {version_info_path}")
    print(f"Wrote {installer_version_path}")
    return 0


def _version_info_text(metadata, file_version: tuple[int, int, int, int]) -> str:
    version_value = ", ".join(str(part) for part in file_version)
    return f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({version_value}),
    prodvers=({version_value}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', '{metadata.publisher}'),
          StringStruct('FileDescription', '{metadata.name}'),
          StringStruct('FileVersion', '{metadata.version}'),
          StringStruct('InternalName', 'QuotaTray'),
          StringStruct('LegalCopyright', 'Copyright (C) 2026 {metadata.publisher}'),
          StringStruct('OriginalFilename', '{metadata.exe_name}'),
          StringStruct('ProductName', '{metadata.name}'),
          StringStruct('ProductVersion', '{metadata.version}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def _installer_version_text(metadata) -> str:
    return f"""#define MyAppName "{metadata.name}"
#define MyAppVersion "{metadata.version}"
#define MyAppPublisher "{metadata.publisher}"
#define MyAppURL "{metadata.url}"
#define MyAppDescription "{metadata.description}"
#define MyAppExeName "{metadata.exe_name}"
#define MyAppId "{{{metadata.app_id}}}"
"""


if __name__ == "__main__":
    raise SystemExit(main())
