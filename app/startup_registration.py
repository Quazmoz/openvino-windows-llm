"""Per-user Windows startup registration for the tray controller."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "OpenVINOWindowsLLM"


class RegistryBackend(Protocol):
    def read(self, key: str, name: str) -> str | None: ...

    def write(self, key: str, name: str, value: str) -> None: ...

    def delete(self, key: str, name: str) -> None: ...


class WinRegBackend:
    def read(self, key: str, name: str) -> str | None:
        if os.name != "nt":
            return None
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_READ) as handle:
                value, _kind = winreg.QueryValueEx(handle, name)
                return str(value)
        except FileNotFoundError:
            return None

    def write(self, key: str, name: str, value: str) -> None:
        if os.name != "nt":
            raise RuntimeError("Start with Windows is only available on Windows.")
        import winreg

        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            key,
            0,
            winreg.KEY_SET_VALUE,
        ) as handle:
            winreg.SetValueEx(handle, name, 0, winreg.REG_SZ, value)

    def delete(self, key: str, name: str) -> None:
        if os.name != "nt":
            return
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                key,
                0,
                winreg.KEY_SET_VALUE,
            ) as handle:
                winreg.DeleteValue(handle, name)
        except FileNotFoundError:
            return


@dataclass(frozen=True)
class StartupRegistrationState:
    enabled: bool
    command: str | None
    location: str = f"HKCU\\{_RUN_KEY}\\{_VALUE_NAME}"


def quote_windows_argument(value: str) -> str:
    text = str(value)
    if not text:
        return '""'
    if not any(char.isspace() or char in '"' for char in text):
        return text
    return subprocess_list2cmdline([text])


def subprocess_list2cmdline(arguments: list[str]) -> str:
    # Python's implementation is the closest representation of CreateProcess parsing.
    import subprocess

    return subprocess.list2cmdline(arguments)


def startup_command(executable: Path, *, portable: bool, open_browser: bool = False) -> str:
    executable = Path(executable).expanduser().resolve()
    command = [str(executable), "--startup"]
    if portable:
        command.append("--portable")
    if not open_browser:
        command.append("--no-browser")
    return subprocess_list2cmdline(command)


class StartupRegistration:
    def __init__(
        self,
        *,
        executable: Path | None = None,
        portable: bool = False,
        backend: RegistryBackend | None = None,
    ) -> None:
        self.executable = Path(executable or sys.executable).expanduser().resolve()
        self.portable = bool(portable)
        self.backend = backend or WinRegBackend()

    @property
    def expected_command(self) -> str:
        return startup_command(self.executable, portable=self.portable, open_browser=False)

    def state(self) -> StartupRegistrationState:
        current = self.backend.read(_RUN_KEY, _VALUE_NAME)
        return StartupRegistrationState(
            enabled=current == self.expected_command,
            command=current,
        )

    def set_enabled(self, enabled: bool) -> StartupRegistrationState:
        if enabled and self.portable:
            raise RuntimeError(
                "Start with Windows is disabled in portable mode. Install the application "
                "per-user before enabling automatic startup."
            )
        if enabled:
            self.backend.write(_RUN_KEY, _VALUE_NAME, self.expected_command)
        else:
            self.backend.delete(_RUN_KEY, _VALUE_NAME)
        return self.state()


class MemoryRegistryBackend:
    """Small deterministic registry substitute for unit tests."""

    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def read(self, key: str, name: str) -> str | None:
        return self.values.get((key, name))

    def write(self, key: str, name: str, value: str) -> None:
        self.values[(key, name)] = value

    def delete(self, key: str, name: str) -> None:
        self.values.pop((key, name), None)
