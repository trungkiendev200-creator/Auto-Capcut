"""Hardware fingerprint — tạo ID duy nhất cho mỗi máy."""

import hashlib
import os
import platform


def get_hardware_id() -> str:
    """Tạo hardware ID từ MachineGuid + CPU + Username. Ổn định qua reboot."""
    machine_guid = _get_machine_guid()
    raw = f"{machine_guid}-{platform.processor()}-{os.getlogin()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _get_machine_guid() -> str:
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography"
        )
        guid, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        return guid
    except Exception:
        return "unknown-machine"
