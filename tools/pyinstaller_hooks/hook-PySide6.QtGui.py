"""Keep only Qt GUI plugins required by QuotaTray's QWidget tray UI.

PyInstaller's QtGui hook collects every plugin of each inferred plugin type.
That set includes optional input-method, SVG, PDF and QML-adjacent plugins.
QuotaTray loads a generated PNG-like QPixmap and a bundled ICO, and uses the
native Windows platform plugin and standard Qt widget style.
"""
from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)

_REQUIRED_PLUGIN_FILES = (
    "/platforms/qwindows.dll",
    "/imageformats/qico.dll",
    "/styles/qmodernwindowsstyle.dll",
)

filtered = []
for source, destination in binaries:
    normalized_source = source.replace("\\", "/").lower()
    normalized_destination = destination.replace("\\", "/").lower()
    is_plugin = "/plugins/" in normalized_destination or "/plugins/" in normalized_source
    if not is_plugin or normalized_source.endswith(_REQUIRED_PLUGIN_FILES):
        filtered.append((source, destination))
    else:
        print(f"[QuotaTray Qt hook] excluded optional plugin: {destination}")
binaries = filtered
