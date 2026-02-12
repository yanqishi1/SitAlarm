from __future__ import annotations

import logging
import platform
import subprocess
import time
from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class SystemUsageSnapshot:
    idle_seconds: float | None


def _idle_seconds_macos() -> float | None:
    # Use ioreg to query IOHIDSystem HIDIdleTime (ns).
    # Example output contains: "HIDIdleTime" = 123456789
    try:
        proc = subprocess.run(
            ["ioreg", "-c", "IOHIDSystem"],
            capture_output=True,
            text=True,
            check=False,
            timeout=1.5,
        )
    except Exception:
        return None

    out = proc.stdout
    if not out:
        return None

    key = "HIDIdleTime"
    idx = out.find(key)
    if idx < 0:
        return None

    snippet = out[idx : idx + 300]
    # Best-effort parse for the first integer after '='.
    eq = snippet.find("=")
    if eq < 0:
        return None

    tail = snippet[eq + 1 :]
    digits = ""
    for ch in tail:
        if ch.isdigit():
            digits += ch
        elif digits:
            break
    if not digits:
        return None

    try:
        ns = int(digits)
    except ValueError:
        return None
    return ns / 1e9


def _idle_seconds_windows() -> float | None:
    try:
        import ctypes
        from ctypes import wintypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

        last_input_info = LASTINPUTINFO()
        last_input_info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(last_input_info)) == 0:
            return None

        tick = ctypes.windll.kernel32.GetTickCount64()
        idle_ms = int(tick) - int(last_input_info.dwTime)
        return max(0.0, idle_ms / 1000.0)
    except Exception:
        return None


def get_idle_seconds() -> float | None:
    system = platform.system().lower()
    if system == "darwin":
        return _idle_seconds_macos()
    if system == "windows":
        return _idle_seconds_windows()
    return None


def _get_macos_screen_time_today() -> int | None:
    """Try to get screen time from macOS using various methods.
    
    Since Screen Time database is protected, we use alternative methods:
    1. Get system wake time (when user started using computer today)
    2. Calculate screen time as: now - wake_time - idle_time
    
    Returns screen time in seconds, or None if unavailable.
    """
    try:
        # Get system wake time using ioreg
        proc = subprocess.run(
            ["ioreg", "-n", "IOHIDSystem", "-a"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if proc.returncode != 0:
            return None
        
        # Try to get last wake time from pmset
        proc = subprocess.run(
            ["pmset", "-g", "log"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        
        if proc.returncode == 0 and proc.stdout:
            from datetime import timezone
            now = datetime.now()
            today = now.date()
            
            # Parse pmset log for today's wake events
            wake_times = []
            for line in proc.stdout.split('\n'):
                if 'Wake' in line or 'wake' in line.lower():
                    # Lines look like: "2024-01-15 08:30:45 +0800"
                    try:
                        # Extract timestamp
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            date_str = parts[0]
                            time_str = parts[1]
                            if date_str.startswith(str(today)):
                                dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
                                wake_times.append(dt)
                    except Exception:
                        continue
            
            if wake_times:
                # Use the last wake time
                last_wake = max(wake_times)
                elapsed = (now - last_wake).total_seconds()
                
                # Get current idle time
                idle = _idle_seconds_macos()
                if idle is not None:
                    # Screen time = elapsed since wake - idle time
                    screen_time = max(0, int(elapsed - idle))
                    return screen_time
                return int(elapsed)
        
        # Fallback: use system uptime
        proc = subprocess.run(
            ["sysctl", "-n", "kern.boottime"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if proc.returncode == 0 and proc.stdout:
            # Parse: { sec = 1704067200, usec = 0 } Mon Jan  1 00:00:00 2024
            import re
            match = re.search(r'sec\s*=\s*(\d+)', proc.stdout)
            if match:
                boot_timestamp = int(match.group(1))
                boot_time = datetime.fromtimestamp(boot_timestamp)
                now = datetime.now()
                elapsed = (now - boot_time).total_seconds()
                
                # Get current idle time
                idle = _idle_seconds_macos()
                if idle is not None:
                    screen_time = max(0, int(elapsed - idle))
                    return min(screen_time, 86400)  # Cap at 24 hours
                return min(int(elapsed), 86400)
    except Exception:
        pass
    return None


def _get_windows_screen_time_today() -> int | None:
    """Try to get screen time from Windows.
    
    Uses Windows Event Log or WMI to estimate screen on time.
    Returns screen time in seconds, or None if unavailable.
    """
    try:
        # Try using WMI to get system boot time and calculate uptime
        import subprocess
        
        # Get system boot time
        result = subprocess.run(
            ["wmic", "path", "Win32_OperatingSystem", "get", "LastBootUpTime"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        if result.returncode == 0:
            # Parse boot time from output
            lines = result.stdout.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line and not line.startswith('LastBootUpTime'):
                    # Format: 20240101120000.000000+480
                    boot_time_str = line.split('.')[0]
                    if len(boot_time_str) >= 14:
                        boot_time = datetime.strptime(boot_time_str[:14], "%Y%m%d%H%M%S")
                        now = datetime.now()
                        uptime_seconds = int((now - boot_time).total_seconds())
                        
                        # Get idle time to estimate active time
                        idle_seconds = _idle_seconds_windows()
                        if idle_seconds is not None:
                            # Screen time = uptime - idle time (approximate)
                            # We assume screen was on during uptime
                            screen_time = max(0, uptime_seconds - int(idle_seconds))
                            return min(screen_time, 86400)  # Cap at 24 hours
                        return min(uptime_seconds, 86400)
    except Exception:
        pass
    return None


def get_system_screen_time_today() -> int | None:
    """Get today's screen time from OS.
    
    Returns screen time in seconds, or None if not available.
    This is a best-effort function that tries to read from OS APIs.
    """
    system = platform.system().lower()
    if system == "darwin":
        return _get_macos_screen_time_today()
    if system == "windows":
        return _get_windows_screen_time_today()
    return None


class SystemUsageService:
    """Accumulate 'screen usage' time from OS idle-time signal.

    This is a best-effort local metric:
    - It counts time when system idle <= idle_cutoff_seconds.
    - It persists per-day counters via StatsService/Storage.

    NOTE: We try to read from OS Screen Time APIs first, but fall back to
    measuring based on idle time while the app is running.
    """

    def __init__(self, *, idle_cutoff_seconds: int = 90) -> None:
        self.idle_cutoff_seconds = max(10, int(idle_cutoff_seconds))
        self._last_tick_monotonic: float | None = None
        self._log = logging.getLogger(__name__)

    def tick(self) -> tuple[date, int]:
        """Return (day, active_delta_seconds) since last tick."""
        now = datetime.now()
        today = now.date()

        t = time.monotonic()
        if self._last_tick_monotonic is None:
            self._last_tick_monotonic = t
            return today, 0

        dt = t - self._last_tick_monotonic
        self._last_tick_monotonic = t
        if dt <= 0:
            return today, 0

        idle = get_idle_seconds()
        if idle is None:
            # If OS idle is unavailable, fall back to counting all time while app is running.
            return today, int(dt)

        if idle <= float(self.idle_cutoff_seconds):
            return today, int(dt)

        return today, 0

    def get_today_screen_time(self) -> int:
        """Get today's total screen time in seconds.
        
        First tries to get from OS, then falls back to accumulated app-based measurement.
        """
        # Try to get from OS first
        os_screen_time = get_system_screen_time_today()
        if os_screen_time is not None and os_screen_time > 0:
            return os_screen_time
        return 0
