"""Collect only QtNetwork itself; QuotaTray uses local IPC, not TLS/TCP."""
from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)

# QLocalServer/QLocalSocket use local Windows IPC. QuotaTray does not use
# QtNetwork's TLS backends or network-information plugins; Codex App Server
# owns all account/network communication in its separate process.
binaries = [
    (source, destination)
    for source, destination in binaries
    if "/plugins/" not in source.replace("\\", "/").lower()
]
