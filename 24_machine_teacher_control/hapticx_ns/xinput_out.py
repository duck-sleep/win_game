"""xinput_out.py — ctypes 调 XInput 双马达振动输出。"""
import ctypes

ERROR_SUCCESS = 0
ERROR_DEVICE_NOT_CONNECTED = 1167


class XINPUT_VIBRATION(ctypes.Structure):
    _fields_ = [("wLeftMotorSpeed", ctypes.c_ushort),
                ("wRightMotorSpeed", ctypes.c_ushort)]


class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [("wButtons", ctypes.c_ushort),
                ("bLeftTrigger", ctypes.c_ubyte),
                ("bRightTrigger", ctypes.c_ubyte),
                ("sThumbLX", ctypes.c_short),
                ("sThumbLY", ctypes.c_short),
                ("sThumbRX", ctypes.c_short),
                ("sThumbRY", ctypes.c_short)]


class XINPUT_STATE(ctypes.Structure):
    class _XINPUT_STATE(ctypes.Union):
        _fields_ = [("Gamepad", XINPUT_GAMEPAD)]
    _anonymous_ = ("state",)
    _fields_ = [("dwPacketNumber", ctypes.c_ulong),
                ("state", _XINPUT_STATE)]


def _load_xinput():
    for dll_name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
        try:
            dll = ctypes.WinDLL(dll_name)
            dll.XInputSetState.argtypes = [ctypes.c_uint,
                                           ctypes.POINTER(XINPUT_VIBRATION)]
            dll.XInputGetState.argtypes = [ctypes.c_uint,
                                           ctypes.POINTER(XINPUT_STATE)]
            return dll
        except OSError:
            continue
    return None


class XInputDevice:
    def __init__(self, user_index=0):
        self.user_index = user_index
        self.dll = _load_xinput()
        self.last_error = None

    @property
    def available(self):
        return self.dll is not None

    def is_connected(self):
        if not self.available:
            return False
        state = XINPUT_STATE()
        rc = self.dll.XInputGetState(self.user_index, ctypes.byref(state))
        return rc == ERROR_SUCCESS

    def set_vibration(self, left, right):
        """left/right ∈ [0,1],内部放大到 0-65535。"""
        if not self.available:
            return False
        vib = XINPUT_VIBRATION(int(max(0.0, min(1.0, left)) * 65535),
                               int(max(0.0, min(1.0, right)) * 65535))
        rc = self.dll.XInputSetState(self.user_index, ctypes.byref(vib))
        if rc != ERROR_SUCCESS:
            self.last_error = rc
            return False
        return True

    def stop(self):
        return self.set_vibration(0.0, 0.0)
