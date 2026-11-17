"""One copy of the app (Tech spec, One copy of the app; DEP-05): starting Sankalan again brings the open window to
the front and restores it.

The first copy creates a small named shared-memory block (``QSharedMemory``, in QtCore: no Qt networking, SEC-1)
holding its window handle. A second copy finds the block, restores that window and exits. Windows frees the block
when the first copy ends, even after a crash.
"""
from __future__ import annotations

import struct
import sys

from PySide6.QtCore import QSharedMemory

KEY = "Sankalan.SingleInstance.v2"
_FORMAT = "<Q"
_SIZE = struct.calcsize(_FORMAT)


class SingleInstance:
    def __init__(self, key: str = KEY):
        self.key = key
        self._mem = QSharedMemory(key)
        self.first = self._mem.create(_SIZE)
        if self.first:
            self._write(0)
        else:
            self._mem = None        # a failed create still holds a handle on Windows until the object goes

    def _write(self, value: int) -> None:
        self._mem.lock()
        try:
            buf = self._mem.data()
            buf[:_SIZE] = struct.pack(_FORMAT, value)
        finally:
            self._mem.unlock()

    def publish(self, window_handle: int) -> None:
        """First copy: record the main window's handle once it is shown."""
        if self.first:
            self._write(int(window_handle))

    def other_window(self) -> int:
        """Second copy: the first copy's window handle (0 if it hasn't shown its window yet)."""
        other = QSharedMemory(self.key)
        if not other.attach(QSharedMemory.AccessMode.ReadOnly):
            return 0
        other.lock()
        try:
            value = struct.unpack(_FORMAT, bytes(other.constData()[:_SIZE]))[0]
        finally:
            other.unlock()
            other.detach()
        return value

    def activate_other(self) -> bool:
        """Second copy: restore the first copy's window and bring it to the front."""
        hwnd = self.other_window()
        if not hwnd or sys.platform != "win32":
            return False
        import ctypes
        user32 = ctypes.windll.user32
        user32.IsIconic.argtypes = [ctypes.c_void_p]
        user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
        if user32.IsIconic(ctypes.c_void_p(hwnd)):
            user32.ShowWindow(ctypes.c_void_p(hwnd), 9)        # SW_RESTORE
        return bool(user32.SetForegroundWindow(ctypes.c_void_p(hwnd)))

    def release(self) -> None:
        if self._mem is not None and self._mem.isAttached():
            self._mem.detach()
