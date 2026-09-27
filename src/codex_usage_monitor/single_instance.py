from __future__ import annotations

from codex_usage_monitor.app_paths import app_data_dir


def instance_server_name() -> str:
    return "QuotaTray.SingleInstance"


def instance_lock_path() -> str:
    return str(app_data_dir() / "QuotaTray.lock")


class SingleInstanceGuard:
    def __init__(self, on_message) -> None:
        self.on_message = on_message
        self.server = None
        self.lock = None

    def try_acquire(self, duplicate_message: bytes = b"show") -> bool:
        from PySide6.QtCore import QLockFile
        from PySide6.QtNetwork import QLocalServer, QLocalSocket

        socket = QLocalSocket()
        socket.connectToServer(instance_server_name())
        if socket.waitForConnected(1000):
            socket.write(duplicate_message)
            socket.flush()
            socket.waitForBytesWritten(1000)
            socket.disconnectFromServer()
            return False

        lock = QLockFile(instance_lock_path())
        lock.setStaleLockTime(30000)
        acquired = lock.tryLock(100)
        if not acquired:
            lock.removeStaleLockFile()
            acquired = lock.tryLock(100)
        if not acquired:
            self._send_best_effort(duplicate_message)
            return False
        self.lock = lock

        self.server = QLocalServer()
        self.server.newConnection.connect(self._on_connection)
        if self.server.listen(instance_server_name()):
            return True

        QLocalServer.removeServer(instance_server_name())
        if self.server.listen(instance_server_name()):
            return True
        self.close()
        return False

    def close(self) -> None:
        from PySide6.QtNetwork import QLocalServer

        if self.server is not None:
            self.server.close()
            self.server = None
        QLocalServer.removeServer(instance_server_name())
        if self.lock is not None:
            self.lock.unlock()
            self.lock = None

    def _on_connection(self) -> None:
        if self.server is None:
            return
        socket = self.server.nextPendingConnection()
        message = b"show"
        if socket is not None:
            if socket.waitForReadyRead(100):
                message = bytes(socket.readAll())
            socket.disconnectFromServer()
        self.on_message(message.decode("utf-8", errors="replace") or "show")

    def _send_best_effort(self, duplicate_message: bytes) -> None:
        from PySide6.QtNetwork import QLocalSocket

        socket = QLocalSocket()
        socket.connectToServer(instance_server_name())
        if socket.waitForConnected(250):
            socket.write(duplicate_message)
            socket.flush()
            socket.waitForBytesWritten(250)
            socket.disconnectFromServer()
