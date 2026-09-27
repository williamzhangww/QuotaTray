# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for QuotaTray.

ICU guard (v0.7.1 regression fix)
---------------------------------
Qt 6.10+/6.11's Qt6Core.dll links against the *Windows system* ICU: it imports 20
unversioned symbols (``ucnv_open``, ``ucnv_toUnicode``,
``UCNV_FROM_U_CALLBACK_SUBSTITUTE``, ...) from ``icuuc.dll``. Only the Windows
system ICU (``C:\\Windows\\System32\\icuuc.dll``, ICU 72.1) exports them.

PyInstaller resolves a DLL import by walking ``os.environ["PATH"]``
(see ``PyInstaller.depend.bindepend.resolve_library_path``). When PATH contains a
third-party ICU build -- e.g. the Codex runtime's bundled poppler
(``%USERPROFILE%\\.cache\\codex-runtimes\\...\\poppler\\Library\\bin``) or a conda
``Library\\bin`` -- PyInstaller binds ``icuuc.dll``/``icudt78.dll`` from *there*
and freezes them into ``_internal``. Those builds are versioned C++ ICU (thousands
of mangled ``icu_78`` exports, zero unversioned ``ucnv_*`` symbols), so at runtime
the frozen copy shadows System32 and ``import PySide6.QtCore`` fails with::

    ImportError: DLL load failed while importing QtCore: 找不到指定的程序

The guard below drops every ICU binary that is not the known-good system one, so
Qt6Core resolves ICU from System32 exactly like the working v0.7.0 payload does.
This keeps the frozen payload correct no matter how PATH is polluted.
"""
import os
import sys

project_root = os.path.abspath(os.getcwd())
sys.path.insert(0, project_root)
from tools.binary_provenance import approved_source_roots, contaminated_native_sources

block_cipher = None
version_info = "build/version_info.txt"


def _filter_optional_qt_binaries(binaries):
    """Drop unused runtimes and reject native binaries from untrusted paths.

    Qt6Core must resolve ``icuuc.dll`` from the Windows system ICU in System32.
    Freezing *any* ICU copy into ``_internal`` is harmful: the loader finds the
    frozen copy first, and third-party ICU builds (poppler's, conda's) do not
    export the unversioned ``ucnv_*`` entry points Qt6Core imports, producing::

        ImportError: DLL load failed while importing QtCore: 找不到指定的程序

    The working v0.7.0 payload does not ship ICU either, so removing it restores
    that exact layout.
    """
    kept = []
    dropped_icu = []
    dropped_optional = []
    dropped_openssl = []
    dropped_msvc = []
    for entry in binaries:
        dest = entry[0].replace("\\", "/")
        name = os.path.basename(dest).lower()
        if name.startswith("icu") and name.endswith(".dll"):
            dropped_icu.append((dest, entry[1]))
            continue
        # QuotaTray is a QWidget/QPainter app and does not create OpenGL
        # contexts. PyInstaller's generic Qt hook adds this QML renderer.
        if name == "opengl32sw.dll":
            dropped_optional.append((dest, entry[1]))
            continue
        # QuotaTray uses only local App Server stdio and Qt local IPC. It does
        # not use Python TLS/hashlib or Qt TLS. The only imports of these
        # OpenSSL 1.1 DLLs in the current analysis are the unused Python
        # _ssl/_hashlib extensions (see spec excludes below).
        if name in {"libssl-1_1.dll", "libcrypto-1_1.dll"}:
            dropped_openssl.append((dest, entry[1]))
            continue
        # Microsoft recommends central deployment of the supported v14 x64
        # Redistributable. Never ship app-local copies from Python/PySide wheels.
        if name.startswith(("msvcp140", "vcruntime140")) and name.endswith(".dll"):
            dropped_msvc.append((dest, entry[1]))
            continue
        kept.append(entry)
    if dropped_icu:
        print("[spec] ICU guard: removed %d ICU binar(ies) from the payload:" % len(dropped_icu))
        for dest, source in dropped_icu:
            print("[spec]   %s  <-  %s" % (dest, source))
        print("[spec]   Qt6Core will load ICU from the Windows system copy in System32.")
    for dest, source in dropped_optional:
        print("[spec] Qt surface: removed unused software OpenGL renderer: %s <- %s" % (dest, source))

    if dropped_openssl:
        print("[spec] OpenSSL: excluded unused Python TLS/hash native runtime binaries:")
        for dest, source in dropped_openssl:
            print("[spec]   %s  <-  %s" % (dest, source))

    if dropped_msvc:
        print("[spec] MSVC runtime: excluded app-local DLLs; system x64 v14 Redistributable is a prerequisite:")
        for dest, source in dropped_msvc:
            print("[spec]   %s  <-  %s" % (dest, source))

    windows_root = os.environ.get("SystemRoot") or r"C:\Windows"
    sdk_root = os.environ.get("WindowsSdkDir") or os.environ.get("WINDOWS_SDK_DIR")
    approved = approved_source_roots(project_root, sys.prefix, windows_root, sdk_root)
    contaminated = contaminated_native_sources(kept, approved)
    if contaminated:
        print("ERROR: contaminated binary provenance")
        for filename, source in contaminated:
            print("  filename: %s" % filename)
            print("  source path: %s" % source)
        raise SystemExit("Refusing to freeze native binaries from unapproved source paths.")
    print("[spec] Native binary provenance: PASS (%d DLL/PYD items; no contaminated sources)." % sum(
        os.path.splitext(entry[0])[1].lower() in {".dll", ".pyd", ".ocx", ".sys"}
        for entry in kept
    ))
    return kept


a = Analysis(
    ["src/codex_usage_monitor/main.py"],
    pathex=["src"],
    binaries=[],
    datas=[("assets/app.ico", "assets")],
    hiddenimports=[
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtNetwork",
    ],
    hookspath=["tools/pyinstaller_hooks"],
    hooksconfig={},
    runtime_hooks=[],
    # The tray UI is QWidget-based; these optional modules are not imported.
    # Keep platform/image plugins selected by PyInstaller's Qt hooks.
    excludes=[
        "PySide6.QtQml",
        "PySide6.QtQmlModels",
        "PySide6.QtQmlWorkerScript",
        "PySide6.QtQuick",
        "PySide6.QtQuickControls2",
        "PySide6.QtQuickWidgets",
        "PySide6.QtVirtualKeyboard",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtOpenGL",
        "PySide6.QtOpenGLWidgets",
        "PySide6.QtSvg",
        "PySide6.QtSvgWidgets",
        # Python's ssl/hashlib extensions statically import OpenSSL 1.1.1t.
        # The app does not use those stdlib APIs; keep this EOL TLS runtime
        # out of the public frozen payload.
        "ssl",
        "_ssl",
        "_hashlib",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

a.binaries = _filter_optional_qt_binaries(a.binaries)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="QuotaTray",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/app.ico",
    version=version_info,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="QuotaTray",
)
