"""Verify the frozen PyInstaller payload is safe to run.

This is the regression check for the v0.7.1 ``QtCore`` DLL failure. It fails
loudly if an ICU binary was frozen into ``_internal``, because the Windows loader
prefers the frozen copy over the system ICU in ``System32`` and third-party ICU
builds (poppler's, conda's) miss the 20 unversioned ``ucnv_*`` entry points that
Qt6Core import can fail with a missing entry point.

Usage:
    python tools/verify_frozen.py dist/QuotaTray
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.binary_provenance import (
    approved_source_roots,
    contaminated_native_sources,
    native_toc_entries,
    read_collect_toc,
)

# The unversioned entry points Qt6Core.dll imports from icuuc.dll.
QT_REQUIRED_ICU_EXPORTS = (
    "UCNV_FROM_U_CALLBACK_SUBSTITUTE",
    "UCNV_TO_U_CALLBACK_SUBSTITUTE",
    "ucnv_cbFromUWriteUChars",
    "ucnv_cbToUWriteUChars",
    "ucnv_close",
    "ucnv_countAvailable",
    "ucnv_fromUCountPending",
    "ucnv_fromUnicode",
    "ucnv_getAvailableName",
    "ucnv_getFromUCallBack",
    "ucnv_getMaxCharSize",
    "ucnv_getName",
    "ucnv_getStandardName",
    "ucnv_getToUCallBack",
    "ucnv_open",
    "ucnv_reset",
    "ucnv_setFromUCallBack",
    "ucnv_setToUCallBack",
    "ucnv_toUCountPending",
    "ucnv_toUnicode",
)

REQUIRED_QT_FILES = (
    "PySide6/QtCore.pyd",
    "PySide6/QtGui.pyd",
    "PySide6/QtWidgets.pyd",
    "PySide6/QtNetwork.pyd",
    "PySide6/Qt6Core.dll",
    "PySide6/Qt6Gui.dll",
    "PySide6/Qt6Widgets.dll",
    "PySide6/Qt6Network.dll",
    "shiboken6/shiboken6.abi3.dll",
    "PySide6/plugins/platforms/qwindows.dll",
    "PySide6/plugins/imageformats/qico.dll",
    "PySide6/plugins/styles/qmodernwindowsstyle.dll",
    "python310.dll",
)


def _pe_exports(path: Path) -> set[str] | None:
    try:
        import pefile
    except ImportError:
        return None
    pe = pefile.PE(str(path), fast_load=True)
    pe.parse_data_directories(
        directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]]
    )
    exports = getattr(pe, "DIRECTORY_ENTRY_EXPORT", None)
    if exports is None:
        return set()
    return {symbol.name.decode() for symbol in exports.symbols if symbol.name}


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: verify_frozen.py <onedir-payload-root> [--toc <COLLECT-00.toc>]")
        return 2

    root = Path(argv[1])
    toc_path: Path | None = None
    if len(argv) == 4 and argv[2] == "--toc":
        toc_path = Path(argv[3])
    elif len(argv) != 2:
        print("usage: verify_frozen.py <onedir-payload-root> [--toc <COLLECT-00.toc>]")
        return 2
    internal = root / "_internal"
    errors: list[str] = []
    notes: list[str] = []

    if not root.is_dir():
        print(f"FAIL: payload root does not exist: {root}")
        return 1
    if not internal.is_dir():
        print(f"FAIL: missing _internal directory under {root}")
        return 1

    # 1. No ICU may be frozen: Qt must use the Windows system ICU.
    frozen_icu = sorted(
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file()
        and p.name.lower().startswith("icu")
        and p.suffix.lower() in {".dll", ".dat"}
    )
    if frozen_icu:
        print("ERROR: bundled ICU detected")
        errors.append(
            "ICU binaries frozen into the payload (must be 0): " + ", ".join(frozen_icu)
        )
    else:
        notes.append("no ICU bundled - Qt6Core resolves icuuc.dll from System32")

    # 2. The Windows system ICU must actually satisfy Qt6Core's imports.
    systemroot = os.environ.get("SystemRoot", r"C:\Windows")
    system_icu = Path(systemroot) / "System32" / "icuuc.dll"
    if not system_icu.is_file():
        errors.append(f"system ICU missing: {system_icu}")
    else:
        exports = _pe_exports(system_icu)
        if exports is None:
            notes.append("pefile unavailable - skipped system ICU export check")
        else:
            missing = [n for n in QT_REQUIRED_ICU_EXPORTS if n not in exports]
            if missing:
                errors.append(
                    f"{system_icu} lacks {len(missing)} export(s) Qt6Core needs: "
                    + ", ".join(missing)
                )
            else:
                notes.append(
                    f"system ICU provides all {len(QT_REQUIRED_ICU_EXPORTS)} required exports"
                )

    # 3. Essential Qt/python runtime files present.
    for rel in REQUIRED_QT_FILES:
        if not (internal / rel).is_file():
            errors.append(f"missing required payload file: _internal/{rel}")
    if not any(root.glob("*.exe")):
        errors.append(f"no executable found in {root}")

    # Release builds must pass the PyInstaller COLLECT TOC so the source path
    # for each bundled native binary can be checked, not guessed from filename.
    if toc_path is not None:
        try:
            entries = read_collect_toc(toc_path)
            project_root = Path(__file__).resolve().parents[1]
            sdk_root = os.environ.get("WindowsSdkDir") or os.environ.get("WINDOWS_SDK_DIR")
            approved = approved_source_roots(
                project_root,
                sys.prefix,
                systemroot,
                sdk_root,
            )
            contaminated = contaminated_native_sources(entries, approved)
        except (OSError, ValueError, SyntaxError) as exc:
            errors.append(f"could not verify native binary provenance from {toc_path}: {exc}")
        else:
            if contaminated:
                print("ERROR: contaminated binary provenance")
                for filename, source in contaminated:
                    print(f"  filename: {filename}")
                    print(f"  source path: {source}")
                errors.append(
                    f"{len(contaminated)} bundled native binary source(s) are outside approved roots"
                )
            else:
                notes.append(
                    f"native binary provenance clean ({len(native_toc_entries(entries))} DLL/PYD items checked)"
                )
    else:
        notes.append("native provenance TOC not supplied (fixture/non-release verification)")

    # 4. Qt Virtual Keyboard is GPL-only in the Qt open-source offering and
    # is not used by this application. Reject modules, plugins, QML payload,
    # or libraries by filename/path regardless of case.
    virtual_keyboard = sorted(
        str(p.relative_to(root))
        for p in root.rglob("*")
        if any(
            marker in p.name.lower() or marker in str(p.relative_to(root)).lower()
            for marker in (
                "virtualkeyboard",
                "virtual_keyboard",
                "qtquickvirtualkeyboard",
                "qt6virtualkeyboard",
            )
        )
    )
    if virtual_keyboard:
        print("ERROR: Qt Virtual Keyboard detected")
        errors.append("Qt Virtual Keyboard payload must be 0: " + ", ".join(virtual_keyboard))
    else:
        notes.append("no Qt Virtual Keyboard modules/plugins/QML payload")

    # These optional UI stacks are not used by the app. Keep them out of the
    # redistributable surface and fail the release if the dependency graph
    # grows to collect them again.
    unused_qt_components = sorted(
        str(p.relative_to(root))
        for p in root.rglob("*")
        if any(
            marker in str(p.relative_to(root)).replace("\\", "/").lower()
            for marker in (
                "qt6qml",
                "qtqml",
                "qml/",
                ".qml",
                "qt6quick",
                "qtquick/",
                "qt6pdf",
                "qtpdf",
                "qt6svg",
                "qtsvg",
                "qt6opengl",
                "qtopengl",
                "opengl32sw.dll",
                "webengine",
                "qt6graphs",
                "qtgraphs",
                "qt6grpc",
                "qtgrpc",
                "qthttpserver",
                "qt6httpserver",
                "qtmqtt",
                "qt6mqtt",
                "qtnetworkauth",
                "qt6networkauth",
            )
        )
    )
    if unused_qt_components:
        print("ERROR: unused Qt modules/plugins detected")
        errors.append("unused Qt components must be 0: " + ", ".join(unused_qt_components))
    else:
        notes.append("no unused QML/Quick/PDF/SVG/OpenGL modules or plugins")

    # This public-prep build explicitly purges the unused Python OpenSSL 1.1
    # runtime; catch both DLLs and their Python extensions anywhere in payload.
    openssl_files = sorted(
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file()
        and p.name.lower()
        in {
            "libssl-1_1.dll",
            "libcrypto-1_1.dll",
            "_ssl.pyd",
            "_hashlib.pyd",
            "qopensslbackend.dll",
        }
    )
    if openssl_files:
        print("ERROR: unused OpenSSL/Python TLS native runtime remains in the frozen payload")
        errors.append("unexpected TLS/hash native binaries: " + ", ".join(openssl_files))
    else:
        notes.append("no OpenSSL 1.1 DLLs bundled")

    # The public installer relies on central deployment of Microsoft's x64
    # v14 Redistributable; fail closed if any app-local runtime copy returns.
    bundled_msvc = sorted(
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file()
        and p.name.lower().endswith(".dll")
        and p.name.lower().startswith(("msvcp140", "vcruntime140"))
    )
    if bundled_msvc:
        print("ERROR: bundled MSVC runtime detected")
        for rel in bundled_msvc:
            print(f"  {rel}")
        errors.append("app-local Microsoft VC runtime DLLs must be 0")
    else:
        notes.append("no app-local MSVC runtime DLLs bundled")

    bundled_ucrt_apiset = sorted(
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file()
        and (
            p.name.lower() == "ucrtbase.dll"
            or (
                p.name.lower().endswith(".dll")
                and p.name.lower().startswith(("api-ms-win-crt-", "api-ms-win-core-"))
            )
        )
    )
    if bundled_ucrt_apiset:
        print("ERROR: bundled UCRT/API-set runtime detected")
        for rel in bundled_ucrt_apiset:
            print(f"  {rel}")
        errors.append("app-local UCRT/API-set DLLs must be 0")
    else:
        notes.append("no app-local UCRT/API-set DLL copies bundled")

    for note in notes:
        print(f"  ok   {note}")
    for err in errors:
        print(f"  FAIL {err}")
    print()
    if errors:
        print(f"RESULT: FAIL ({len(errors)} problem(s))")
        return 1
    print("RESULT: PASS - frozen payload will load PySide6.QtCore")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
