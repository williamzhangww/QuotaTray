from __future__ import annotations

import ctypes
from ctypes import wintypes

ERROR_ALREADY_EXISTS = 183
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258

MUTEX_NAME = "Local\\QuotaTray.SingleInstance.Mutex"
SHOW_EVENT_NAME = "Local\\QuotaTray.SingleInstance.Show"
QUIT_EVENT_NAME = "Local\\QuotaTray.SingleInstance.Quit"


class WindowsInstanceGuard:
    def __init__(self) -> None:
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._mutex = None
        self._show_event = None
        self._quit_event = None
        self._configure()

    def try_acquire(self) -> bool:
        self._mutex = self._kernel32.CreateMutexW(None, True, MUTEX_NAME)
        if not self._mutex:
            return True
        return ctypes.get_last_error() != ERROR_ALREADY_EXISTS

    def notify_existing(self, quit_requested: bool) -> None:
        event_name = QUIT_EVENT_NAME if quit_requested else SHOW_EVENT_NAME
        event = self._kernel32.CreateEventW(None, False, False, event_name)
        if event:
            self._kernel32.SetEvent(event)
            self._kernel32.CloseHandle(event)

    def wait_until_released(self, timeout_ms: int) -> bool:
        if not self._mutex:
            return True
        result = self._kernel32.WaitForSingleObject(self._mutex, timeout_ms)
        if result == WAIT_OBJECT_0:
            self._kernel32.ReleaseMutex(self._mutex)
            return True
        return result != WAIT_TIMEOUT

    def create_events(self) -> None:
        self._show_event = self._kernel32.CreateEventW(None, False, False, SHOW_EVENT_NAME)
        self._quit_event = self._kernel32.CreateEventW(None, False, False, QUIT_EVENT_NAME)

    def consume_show(self) -> bool:
        return self._consume(self._show_event)

    def consume_quit(self) -> bool:
        return self._consume(self._quit_event)

    def close(self) -> None:
        for handle in (self._show_event, self._quit_event, self._mutex):
            if handle:
                self._kernel32.CloseHandle(handle)
        self._show_event = None
        self._quit_event = None
        self._mutex = None

    def _consume(self, handle) -> bool:
        if not handle:
            return False
        return self._kernel32.WaitForSingleObject(handle, 0) == WAIT_OBJECT_0

    def _configure(self) -> None:
        self._kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        self._kernel32.CreateMutexW.restype = wintypes.HANDLE
        self._kernel32.CreateEventW.argtypes = [
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        ]
        self._kernel32.CreateEventW.restype = wintypes.HANDLE
        self._kernel32.SetEvent.argtypes = [wintypes.HANDLE]
        self._kernel32.SetEvent.restype = wintypes.BOOL
        self._kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self._kernel32.WaitForSingleObject.restype = wintypes.DWORD
        self._kernel32.ReleaseMutex.argtypes = [wintypes.HANDLE]
        self._kernel32.ReleaseMutex.restype = wintypes.BOOL
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel32.CloseHandle.restype = wintypes.BOOL
