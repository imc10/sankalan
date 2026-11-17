"""Create or remove Sankalan's Start menu and desktop shortcuts on Windows (run-from-source fallback only).

    python shortcuts.py --dest "%LOCALAPPDATA%\\Programs\\Sankalan"           create
    python shortcuts.py --dest "%LOCALAPPDATA%\\Programs\\Sankalan" --remove  remove

Done in Python (via the Windows shell's own ShellLink object) rather than PowerShell: with Smart App
Control on, PowerShell runs scripts in Constrained Language Mode, which blocks creating shortcuts.
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid

CSIDL_PROGRAMS = 0x02
CSIDL_DESKTOPDIRECTORY = 0x10
CLSID_SHELL_LINK = "00021401-0000-0000-C000-000000000046"
IID_ISHELL_LINK_W = "000214F9-0000-0000-C000-000000000046"
IID_IPERSIST_FILE = "0000010B-0000-0000-C000-000000000046"
NAME = "Sankalan.lnk"


def _guid(s):
    import ctypes

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort), ("Data3", ctypes.c_ushort),
                    ("Data4", ctypes.c_ubyte * 8)]

    u = uuid.UUID(s)
    return GUID(u.time_low, u.time_mid, u.time_hi_version, (ctypes.c_ubyte * 8)(*u.bytes[8:]))


def shell_folder(csidl: int) -> str:
    """Start menu Programs / Desktop, including a Desktop redirected to OneDrive."""
    import ctypes
    buf = ctypes.create_unicode_buffer(32768)
    hr = ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf)
    if hr != 0:
        raise OSError(f"SHGetFolderPathW failed ({hr:#x})")
    return buf.value


def _method(obj, index, *argtypes):
    import ctypes
    from ctypes import POINTER, c_void_p
    vtbl = ctypes.cast(obj, POINTER(POINTER(c_void_p))).contents
    return ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, *argtypes)(vtbl[index])


def create_shortcut(lnk_path, target, arguments, workdir, icon, description):
    import ctypes
    from ctypes import POINTER, byref, c_void_p, wintypes
    ole32 = ctypes.windll.ole32
    ole32.CoInitialize(None)
    try:
        link = c_void_p()
        clsid, iid = _guid(CLSID_SHELL_LINK), _guid(IID_ISHELL_LINK_W)
        hr = ole32.CoCreateInstance(byref(clsid), None, 1, byref(iid), byref(link))   # CLSCTX_INPROC_SERVER
        if hr != 0:
            raise OSError(f"CoCreateInstance(ShellLink) failed ({hr & 0xFFFFFFFF:#x})")
        try:
            # IShellLinkW vtable: 7 SetDescription, 9 SetWorkingDirectory, 11 SetArguments,
            # 17 SetIconLocation, 20 SetPath
            _method(link, 20, wintypes.LPCWSTR)(link, target)
            _method(link, 11, wintypes.LPCWSTR)(link, arguments)
            _method(link, 9, wintypes.LPCWSTR)(link, workdir)
            _method(link, 17, wintypes.LPCWSTR, ctypes.c_int)(link, icon, 0)
            _method(link, 7, wintypes.LPCWSTR)(link, description)
            persist = c_void_p()
            iid_pf = _guid(IID_IPERSIST_FILE)
            _method(link, 0, c_void_p, POINTER(c_void_p))(link, ctypes.addressof(iid_pf), byref(persist))
            try:
                _method(persist, 6, wintypes.LPCWSTR, wintypes.BOOL)(persist, lnk_path, True)   # IPersistFile::Save
            finally:
                _method(persist, 2)(persist)
        finally:
            _method(link, 2)(link)
    finally:
        ole32.CoUninitialize()


def shortcut_paths():
    return [os.path.join(shell_folder(CSIDL_PROGRAMS), NAME), os.path.join(shell_folder(CSIDL_DESKTOPDIRECTORY), NAME)]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", required=True)
    ap.add_argument("--remove", action="store_true")
    a = ap.parse_args(argv)
    if os.name != "nt":
        print("Shortcuts can only be made on Windows.")
        return 2
    dest = os.path.abspath(a.dest)
    paths = shortcut_paths()
    if a.remove:
        for p in paths:
            if os.path.exists(p):
                os.remove(p)
        print("Shortcuts removed.")
        return 0
    target = os.path.join(dest, "venv", "Scripts", "pythonw.exe")
    launcher = os.path.join(dest, "app", "Sankalan.pyw")
    icon = os.path.join(dest, "app", "sankalan.ico")
    for p in (target, launcher):
        if not os.path.exists(p):
            print(f"Missing: {p}")
            return 1
    for p in paths:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        create_shortcut(p, target, f'"{launcher}"', os.path.join(dest, "app"), icon, "Sankalan")
        if not os.path.exists(p):
            print(f"Could not create {p}")
            return 1
    print("Shortcuts created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
