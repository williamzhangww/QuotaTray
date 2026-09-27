"""Launch a frozen EXE detached and dump any PyInstaller error dialog.

Run under Python 3.10:
    python tools/probe_frozen.py <exe-path> [--args "..."]
"""
from __future__ import annotations

import ctypes
import os
import sys
import time
from ctypes import wintypes
from pathlib import Path

user32 = ctypes.WinDLL("user32", use_last_error=True)

EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
EnumChildProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
user32.EnumChildWindows.argtypes = [wintypes.HWND, EnumChildProc, wintypes.LPARAM]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPWSTR]
user32.IsWindowVisible.argtypes = [wintypes.HWND]


def window_text(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(32768)
    user32.GetWindowTextW(hwnd, buf, 32768)
    if not buf.value:
        # WM_GETTEXT for controls that do not expose text via GetWindowText.
        user32.SendMessageW(hwnd, 0x000D, 32768, buf)
    return buf.value


def windows_for_pid(pid: int) -> list[tuple[int, str, str, bool]]:
    found: list[tuple[int, str, str, bool]] = []

    @EnumWindowsProc
    def cb(hwnd, _lparam):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            found.append(
                (hwnd, window_text(hwnd), cls.value, bool(user32.IsWindowVisible(hwnd)))
            )
        return True

    user32.EnumWindows(cb, 0)
    return found


def dialog_text(dlg: int) -> str:
    parts: list[str] = []

    @EnumChildProc
    def cb(hwnd, _lparam):
        text = window_text(hwnd)
        if text:
            parts.append(text)
        return True

    user32.EnumChildWindows(dlg, cb, 0)
    return "\n---\n".join(parts)


def _token_report(pid: int) -> str:
    """Report the security context a process is running under."""
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32.LookupAccountSidW.argtypes = [
        wintypes.LPCWSTR, ctypes.c_void_p, wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD), wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetSidSubAuthorityCount.argtypes = [ctypes.c_void_p]
    advapi32.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
    advapi32.GetSidSubAuthority.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    advapi32.GetSidSubAuthority.restype = ctypes.POINTER(ctypes.c_ulong)

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    TOKEN_QUERY = 0x0008
    TokenUser = 1
    TokenIntegrityLevel = 25

    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return f"OpenProcess failed err={ctypes.get_last_error()}"
    try:
        tok = wintypes.HANDLE()
        if not advapi32.OpenProcessToken(h, TOKEN_QUERY, ctypes.byref(tok)):
            return f"OpenProcessToken failed err={ctypes.get_last_error()}"
        try:
            out = []
            for cls, label in ((TokenUser, "user"), (TokenIntegrityLevel, "integrity")):
                size = wintypes.DWORD(0)
                advapi32.GetTokenInformation(tok, cls, None, 0, ctypes.byref(size))
                buf = ctypes.create_string_buffer(size.value)
                if advapi32.GetTokenInformation(tok, cls, buf, size.value, ctypes.byref(size)):
                    if cls == TokenIntegrityLevel:
                        # TOKEN_MANDATORY_LABEL { SID_AND_ATTRIBUTES { PSID Sid; DWORD Attributes } }
                        sid_ptr = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0]
                        sub = advapi32.GetSidSubAuthorityCount(sid_ptr)
                        n = ctypes.cast(sub, ctypes.POINTER(ctypes.c_ubyte))[0]
                        rid = advapi32.GetSidSubAuthority(sid_ptr, n - 1)
                        out.append(f"{label}=RID{ctypes.cast(rid, ctypes.POINTER(ctypes.c_ulong))[0]}")
                    else:
                        sid_ptr = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0]
                        name = ctypes.create_unicode_buffer(256)
                        dom = ctypes.create_unicode_buffer(256)
                        nl = wintypes.DWORD(256)
                        dl = wintypes.DWORD(256)
                        use = wintypes.DWORD(0)
                        advapi32.LookupAccountSidW(None, sid_ptr, name, ctypes.byref(nl),
                                                   dom, ctypes.byref(dl), ctypes.byref(use))
                        out.append(f"{label}={dom.value}\\{name.value}")
            return " ".join(out)
        finally:
            kernel32.CloseHandle(tok)
    finally:
        kernel32.CloseHandle(h)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: probe_frozen.py <exe> [args...]")
        return 2

    exe = Path(argv[1])
    args = " ".join(argv[2:])

    import subprocess

    # Optional isolation: point LOCALAPPDATA somewhere fresh so the probe can
    # never disturb the user's real database/settings/logs.
    env = dict(os.environ)
    data_root = env.get("CUM_PROBE_LOCALAPPDATA")
    if data_root:
        env["LOCALAPPDATA"] = data_root
        Path(data_root).mkdir(parents=True, exist_ok=True)
        print(f"isolated LOCALAPPDATA -> {data_root}")

    proc = subprocess.Popen(
        [str(exe), *argv[2:]],
        cwd=str(exe.parent),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=0x00000008 | 0x00000200,  # DETACHED_PROCESS | NEW_PROCESS_GROUP
    )
    print(f"launched pid={proc.pid} exe={exe} args={args!r}")
    print(f"  parent(this process) token: {_token_report(os.getpid())}")
    print(f"  child token:                {_token_report(proc.pid)}")

    for elapsed in range(0, 31, 3):
        time.sleep(3)
        alive = proc.poll() is None
        wins = windows_for_pid(proc.pid)
        visible = [w for w in wins if w[3]]
        print(f"  t+{elapsed + 3:>2}s alive={alive} windows={len(wins)} visible={len(visible)}")
        for hwnd, title, cls, vis in visible:
            print(f"      hwnd={hwnd} class={cls} visible={vis} title={title!r}")
            if "exception" in title.lower() or "error" in title.lower():
                print("      ---- dialog content ----")
                for line in dialog_text(hwnd).splitlines():
                    print(f"      {line}")
        if not alive:
            print(f"  process exited rc={proc.returncode}")
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
