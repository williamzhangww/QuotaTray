# QuotaTray 0.8.0 runtime component inventory

Scope: Windows x64 public-prep frozen payload. The checked clean build contains 27 native DLL/PYD items. Source provenance is checked from the PyInstaller COLLECT TOC by `tools/verify_frozen.py`.

## Required native runtime

| Component | Payload | Source / role | Bundled |
|---|---|---|---|
| CPython | `python310.dll`, `python3.dll`, `base_library.zip` | Python 3.10.11 runtime and standard library | Yes |
| Python native extensions | `_bz2.pyd`, `_ctypes.pyd`, `_decimal.pyd`, `_lzma.pyd`, `_queue.pyd`, `_socket.pyd`, `_sqlite3.pyd`, `select.pyd`, `unicodedata.pyd` | Python 3.10.11 `DLLs` | Yes |
| SQLite | `sqlite3.dll` | Python 3.10.11 `DLLs` | Yes |
| libffi | `libffi-7.dll` | Python 3.10.11 `DLLs` | Yes |
| PySide6 | `QtCore.pyd`, `QtGui.pyd`, `QtNetwork.pyd`, `QtWidgets.pyd`, `pyside6.abi3.dll` | PySide6 6.11.2 | Yes |
| shiboken6 | `Shiboken.pyd`, `shiboken6.abi3.dll` | shiboken6 6.11.2 | Yes |
| Qt | `Qt6Core.dll`, `Qt6Gui.dll`, `Qt6Widgets.dll`, `Qt6Network.dll` | Qt 6.11.2 | Yes |
| Qt platform/image/style plugins | `qwindows.dll`, `qico.dll`, `qmodernwindowsstyle.dll` | PySide6 6.11.2 | Yes |
| Translations | 96 `.qm` files listed in `Qt-6.11.2-runtime-manifest.txt` | PySide6 6.11.2 | Yes |
| PyInstaller bootloader | Embedded in `QuotaTray.exe` | PyInstaller 6.22.3 | Yes |

The 27 native items are: `python310.dll`, `python3.dll`; `_bz2.pyd`, `_ctypes.pyd`, `_decimal.pyd`, `_lzma.pyd`, `_queue.pyd`, `_socket.pyd`, `_sqlite3.pyd`, `select.pyd`, `unicodedata.pyd`; `sqlite3.dll`, `libffi-7.dll`; `PySide6/QtCore.pyd`, `QtGui.pyd`, `QtNetwork.pyd`, `QtWidgets.pyd`, `pyside6.abi3.dll`; `shiboken6/Shiboken.pyd`, `shiboken6.abi3.dll`; `PySide6/Qt6Core.dll`, `Qt6Gui.dll`, `Qt6Network.dll`, `Qt6Widgets.dll`; `PySide6/plugins/platforms/qwindows.dll`, `plugins/imageformats/qico.dll`, and `plugins/styles/qmodernwindowsstyle.dll`.

PE import analysis of the new frozen components found direct MSVC imports in: `_bz2.pyd`, `_ctypes.pyd`, `_decimal.pyd`, `_lzma.pyd`, `_queue.pyd`, `_socket.pyd`, `_sqlite3.pyd`, `select.pyd`, `unicodedata.pyd`, `python310.dll`, `sqlite3.dll`, and `libffi-7.dll` (`VCRUNTIME140.dll`); `Qt6Core.dll`, `Qt6Gui.dll`, `Qt6Network.dll`, `Qt6Widgets.dll`, `QtNetwork.pyd`, `pyside6.abi3.dll`, `shiboken6.abi3.dll`, `qwindows.dll`, and `qmodernwindowsstyle.dll` (MSVCP140 and/or VCRUNTIME140/140_1/140_2); `Shiboken.pyd` (VCRUNTIME140/140_1); and `qico.dll` (VCRUNTIME140). The Windows System32 copies matching these imports have version 14.50.35719.0 on the inspected machine, which also reports x64 Redistributable `Installed=1`, `Version=v14.50.35719.00`, `Major=14`, `Minor=50`, `Bld=35719`. The numeric system version is newer than the imports' prior maximum observed build, 14.44.35211. These imports therefore have matching central runtime DLLs on this machine; this is evidenced by PE imports and file versions, not merely by app launch.

## System prerequisite / not bundled

QuotaTray requires Microsoft Visual C++ Redistributable (x64), v14.44 or newer. The installer checks `HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64` (64-bit registry view), including `Installed`, `Version`, `Major`, `Minor`, and `Bld`. If missing or too old it stops and links to Microsoft's official x64 package: https://aka.ms/vc14/vc_redist.x64.exe. QuotaTray does not bundle or install the redistributable.

The previously bundled Python/PySide6/shiboken6 copies of `MSVCP140*.dll` and `VCRUNTIME140*.dll` are excluded by the PyInstaller spec collection layer. `tools/verify_frozen.py` rejects them in any case or directory and prints `ERROR: bundled MSVC runtime detected` with paths. No post-build deletion is used.

## Absent optional or unrelated native components

The verified public payload must contain none of:

- OpenSSL: `libssl-1_1.dll`, `libcrypto-1_1.dll`, `_ssl.pyd`, `_hashlib.pyd`, `qopensslbackend.dll`.
- ICU: any app-local ICU DLL or data file; Qt resolves system ICU through Windows.
- Qt Virtual Keyboard, QML, Quick, PDF, WebEngine, SVG, OpenGL, Graphs, GRPC, HTTP Server, MQTT, or Network Authorization modules/plugins (except `qwindows`, `qico`, and `qmodernwindowsstyle` explicitly required above).
- `MSVCP140*.dll`, `VCRUNTIME140*.dll`.
- App-local `ucrtbase.dll`, `api-ms-win-crt-*.dll`, or `api-ms-win-core-*.dll` copies from unrelated build caches.
- Codex runtime, libheif, Poppler, Conda, or other unrelated native binaries. Controlled build PATH and provenance checks enforce this.

The source archives and conservative module-level third-party attribution coverage for the Qt/PySide6 LGPLv3 distribution are recorded in `THIRD_PARTY_NOTICES.md` and `Qt-6.11.2-third-party/`. The exact Windows wheel/build SBOM was not present in the installed PySide wheels; do not interpret the conservative table as a binary-specific component claim. The PyInstaller bootloader exception text remains in `PyInstaller-COPYING.txt` and must continue to match the shipped bootloader.
