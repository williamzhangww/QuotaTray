# Third-party notices

This inventory describes the QuotaTray 0.8.1 Windows x64 frozen payload produced with Python 3.10.11 and a controlled build PATH. It is a factual package inventory, not legal advice or a compliance certification. Component/source correspondence is checked against PyInstaller's COLLECT TOC, file version metadata, and PE import tables. The latest clean frozen build has 27 native DLL/PYD items and passed the provenance guard.

## Microsoft Visual C++ Redistributable (x64) system prerequisite / not bundled

QuotaTray requires Microsoft's supported Visual C++ Redistributable (x64), v14.44 or newer. QuotaTray does **not** bundle Microsoft VC runtime DLLs and does not download or install the prerequisite. The per-user installer checks Microsoft's x64 registry state and stops with a Microsoft download link if the prerequisite is missing or too old. Users can obtain the package from [Microsoft's official x64 download](https://aka.ms/vc14/vc_redist.x64.exe).

## QuotaTray

QuotaTray application source is licensed under MIT; see the repository-root `LICENSE`. That license does not apply to third-party components or to the generated installer as a whole.

## Qt and Qt for Python

QuotaTray dynamically links to Qt 6.11.2 through PySide6 6.11.2 and shiboken6 6.11.2. The installed v0.8.1 payload contains `Qt6Core.dll`, `Qt6Gui.dll`, `Qt6Widgets.dll`, `Qt6Network.dll`; PySide6 modules `QtCore.pyd`, `QtGui.pyd`, `QtWidgets.pyd`, `QtNetwork.pyd`; bindings `pyside6.abi3.dll`, `Shiboken.pyd`, `shiboken6.abi3.dll`; and plugins `qwindows.dll`, `qico.dll`, `qmodernwindowsstyle.dll`. The exact list is in `licenses/Qt-6.11.2-runtime-manifest.txt`.

The PySide6 6.11.2 and shiboken6 6.11.2 wheel metadata declares `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`. This distribution uses the LGPLv3 option for the dynamically linked Qt/PySide6 components; `licenses/LGPL-3.0.txt` contains the GNU license text. The original PySide/shiboken source notices are retained under `licenses/Qt-6.11.2-third-party/`. No standalone GPL-only Qt module is present in the installed payload. The app's MIT license does not replace any third-party terms.

### Qt module and plugin attribution

Qt's published 6.11.2 module documentation says to acknowledge components actually shipped and labels the module component lists as items Qt modules “may contain”. The installed PySide wheels contain license metadata but no SPDX or CycloneDX SBOM for this Windows wheel/build configuration. The Qt source archives contain REUSE licensing metadata, but they do not identify the exact objects linked into these prebuilt DLLs. Accordingly, the following is **conservative attribution coverage** based on the actual shipped module surface and Qt's published module-level lists; entries are not claims that every listed component is present in these specific binaries.

| Shipped Qt module | Conservative third-party attribution coverage |
|---|---|
| QtCore | Apache Tika MIME type definitions (Apache-2.0); BLAKE2 (CC0-1.0 or Apache-2.0); zlib (Zlib); Easing Equations (BSD-3-Clause); double-conversion (BSD-3-Clause); PCRE2 and SLJIT (BSD-2-Clause / BSD-3-Clause with PCRE2 binary-like package exception); SHA-3/Keccak (CC0-1.0 and BSD-2-Clause); SHA-384/SHA-512 (BSD-3-Clause); SipHash (CC0-1.0); TinyCBOR (MIT); Unicode data (Unicode-3.0); forkfd (MIT); tl::expected (CC0-1.0); MD4, MD5, SHA-1 (public domain). The macOS-only event dispatcher entry is not included in this Windows attribution set. |
| QtGui | Adobe Glyph List (BSD-3-Clause); FreeType and its BDF/PCF/zlib portions (FTL or GPL-2.0-only, MIT, MIT-open-group, Zlib); D3D12 Memory Allocator (MIT); DejaVu font data (Bitstream-Vera); Emoji Segmenter (Apache-2.0); HarfBuzz (MIT); libjpeg-turbo (IJG and BSD-3-Clause); libpng (Libpng and libpng-2.0); MD4C (MIT); D3D12 mipmap generator (MIT); OpenGL ES/OpenGL headers (MIT-Khronos-old); Pixman (MIT); smooth-scaling code (BSD-2-Clause and Imlib2); Vulkan API Registry (Apache-2.0 or MIT); Vulkan Memory Allocator (MIT); WebGradients (MIT); Wintab API (LCS-Telegraphics); sRGB profile data (ICC License). |
| QtNetwork | Public Suffix List data (MPL-2.0); libpsl (BSD-3-Clause). |
| QtWidgets | Qt's 6.11.2 third-party module listing has no separate QtWidgets third-party entries. Qt's module license still applies. |

The shipped `qwindows`, `qico`, and `qmodernwindowsstyle` plugins are listed in the runtime manifest. The Qt documentation does not list separate third-party components for these specific plugin binaries. Separate Qt Image Formats plugins and their libtiff/WebP components are not included. No attribution is added for unshipped Qt modules such as WebEngine, PDF, Virtual Keyboard, QML/Quick, SVG, or OpenGL modules.

The corresponding original Qt license texts and source notices are included under `licenses/Qt-6.11.2-third-party/`. Filenames encode the path inside the named upstream source archive (path separators are represented by `__`); `SOURCE-MAP.txt` records each exact archive member and the extracted file's SHA256. Qt Base's SPDX license texts are preserved verbatim from its `LICENSES/` directory. Component-specific original files are preserved verbatim from their source subtrees. The PySide/shiboken `COPYING` files are retained as source-origin material and do not replace the LGPLv3 distribution choice stated above.

Acknowledgement: QuotaTray uses Qt 6.11.2 and Qt for Python (PySide6/shiboken6) 6.11.2 from The Qt Company. Qt and Qt for Python are dynamically linked as replaceable DLLs in the per-user install directory; the installer does not intentionally prevent replacement.

For QuotaTray v0.8.1, the corresponding source archives are provided as assets with the QuotaTray GitHub Release:

| Exact source archive | Official Qt download origin | Size (bytes) | SHA256 |
|---|---|---:|---|
| `qtbase-everywhere-src-6.11.2.tar.xz` | [Qt 6.11.2 QtBase submodule archive](https://download.qt.io/archive/qt/6.11/6.11.2/submodules/qtbase-everywhere-src-6.11.2.tar.xz) | 50582668 | `5b2e00eccaf5a4d8c14134ffa0ea8dfd0a35ae1ffc7f8d87fa4305a1ed23cf22` |
| `pyside-setup-everywhere-src-6.11.2.tar.xz` | [Qt for Python 6.11.2 source archive](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.2-src/pyside-setup-everywhere-src-6.11.2.tar.xz) | 18053248 | `cba47efbaad1bedd529725cbc14e21f156c7a19366f07b3edfbb076ffd7afdf8` |

These exact official Qt source archives accompany the QuotaTray v0.8.1 installer as GitHub Release assets. Their published byte sizes and SHA256 digests must match this table and `licenses/Qt-6.11.2-third-party/SOURCE-MAP.txt`.

## Runtime component inventory

The exact component, filename, observed version, provenance, license status, and bundle status are recorded in [`licenses/QuotaTray-0.8.1-runtime-inventory.md`](licenses/QuotaTray-0.8.1-runtime-inventory.md). The Qt filename inventory, including all shipped Qt translations, is in [`licenses/Qt-6.11.2-runtime-manifest.txt`](licenses/Qt-6.11.2-runtime-manifest.txt).

## License and notice files in this repository

- `LICENSE`: QuotaTray source, MIT.
- `licenses/LGPL-3.0.txt`: GNU Lesser GPL v3 text from the Free Software Foundation, selected for this dynamically linked Qt/PySide6 distribution.
- `licenses/Qt-6.11.2-third-party/`: 55 verbatim license texts/notices from the official QtBase 6.11.2 and PySide 6.11.2 source archives. `SOURCE-MAP.txt` identifies archive paths and hashes.
- `licenses/Python-PSF-License.txt`: CPython 3.10.11 distribution license text for the bundled Python runtime.
- `licenses/PyInstaller-COPYING.txt`: PyInstaller 6.22.3 wheel's original `licenses/COPYING.txt`, including the GPL-2.0-or-later bootloader exception and Apache-2.0 runtime-hook notice. The exception must remain applicable to the shipped bootloader.
- `licenses/PyInstaller-hooks-contrib-LICENSE.txt`: original license from pyinstaller-hooks-contrib 2026.7 wheel metadata; this is build-time tooling, not a runtime dependency.
- `licenses/Qt-6.11.2-runtime-manifest.txt`: exact shipped Qt DLLs, Python extension modules, plugins, and translations.
- `licenses/QuotaTray-0.8.1-runtime-inventory.md`: observed binary versions, PE dependencies, provenance review, the system VC runtime prerequisite, and excluded optional Python TLS modules.

No standalone GPL-only Qt component is shipped. The LGPLv3 terms are the selected distribution route; the LGPL text refers to GPL terms as part of its own terms. Because an exact Windows wheel/build SBOM is not available, the module-level attribution table is conservative and must be checked again for future builds.

## OpenSSL files excluded from this binary

The final `dist/QuotaTray` payload and installer contain none of `libssl-1_1.dll`, `libcrypto-1_1.dll`, `_ssl.pyd`, `_hashlib.pyd`, or `qopensslbackend.dll`. PE analysis of the previous build identified Python `_ssl.pyd` and `_hashlib.pyd` as the direct importers of OpenSSL 1.1.1t; Qt6Network had no direct import of those DLLs. The application uses Codex App Server stdio and Qt local IPC and does not call Python TLS/hash APIs or Qt TLS APIs. The spec excludes the unused Python extensions and the old DLLs at collection time, and release verification rejects their reappearance.

This statement applies only to this frozen QuotaTray artifact. It is not a claim that the Python distribution, OpenAI Codex, or any external process has no OpenSSL dependency.

## Windows runtime provenance

The earlier payload's API-set/UCRT DLLs were resolved from a Codex runtime cache's libheif directory. PyInstaller's Windows dependency resolver searches PATH; that contaminated path preceded Windows system directories and provided DLLs with matching names. The release script now replaces inherited PATH with the selected Python 3.10.11 environment, its Python/PySide6/shiboken directories, and Windows system paths. It removes inherited Python/Qt/QML path overrides and disables Python user-site packages. Inno Setup is separately staged under the user's local build-tools directory, hash-checked, and run with a minimal Windows PATH.

The new COLLECT TOC and final frozen payload contain no app-local `ucrtbase.dll`, `api-ms-win-crt-*.dll`, or `api-ms-win-core-*.dll`. No post-build deletion or filename-only filtering was used. Native binary provenance is checked both in `QuotaTray.spec` and in `tools/verify_frozen.py`; any DLL/PYD outside the project, selected Python environment, Windows system, or configured Windows SDK roots fails with `ERROR: contaminated binary provenance` and lists its filename and source path. Explicitly forbidden source markers include Codex cache, Poppler, libheif, and unrelated Conda roots.

## Installer tool

The Windows setup executable is generated with Inno Setup 7.1.0. The project distributes the generated QuotaTray installer, not the Inno Setup compiler or development environment. Inno Setup's applicable license permits use for any purpose including commercial applications (owner-verified for this task); acknowledgement is appreciated but not required. The installer is not itself licensed under the QuotaTray MIT license.

## Maintenance notes

- Reconcile future Qt modules, plugins, translations, bundled third-party notices, and their LGPLv3 mapping against the exact build inventory whenever the build configuration changes.
- Keep the exact Qt 6.11.2 and PySide6/shiboken6 6.11.2 source archives attached to the QuotaTray v0.8.1 GitHub Release. Their official URLs and hashes are recorded above.
- Revalidate the Microsoft Visual C++ Redistributable prerequisite policy and PyInstaller bootloader exception notice when the supported build environment changes.
