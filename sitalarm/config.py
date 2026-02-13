from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

APP_NAME = "SitAlarm"


@dataclass(frozen=True)
class AppSettings:
    # Detection interval in seconds (supports sub-minute scheduling).
    # Note: older versions stored `capture_interval_minutes`; we migrate in SettingsService.
    capture_interval_seconds: int = 300
    # UI is opaque by default. (Kept for backward compatibility with older DB keys.)
    ui_opacity: float = 1.0
    # Camera index for OpenCV VideoCapture.
    camera_index: int = 0
    # Reminder method when posture is incorrect:
    # - "dim_screen": dim via overlay and restore (default)
    # - "popup": show popup/toast
    reminder_method: str = "dim_screen"
    # Cooldown policy (minutes). UI no longer exposes this knob.
    reminder_cooldown_minutes: int = 3
    screen_time_enabled: bool = False
    screen_time_threshold_minutes: int = 60
    retention_days: int = 7
    head_ratio_threshold: float = 0.0
    # Detection strictness mode:
    # - "strict": use threshold as-is
    # - "normal": threshold * 1.1
    # - "loose":  threshold * 1.2
    detection_mode: str = "normal"
    # Compute backend preference for MediaPipe runtime.
    # - "cpu": force CPU inference
    # - "gpu": allow GPU acceleration when available
    compute_device: str = "cpu"
    # MediaPipe Pose model complexity:
    # - 0: Lite (fast, lower Z-axis accuracy)
    # - 1: Full (balanced, better Z-axis accuracy) - recommended for non-realtime detection
    # - 2: Heavy (slow, best Z-axis accuracy)
    pose_model_complexity: int = 1
    # Camera angle mode affects detection strategy:
    # - "upper_body": only shoulders and above visible, disable hunchback detection
    # - "full_body": full body visible, enable all detection types
    camera_angle_mode: str = "upper_body"
    # Calibrated head forward ratio threshold (0.0 means not calibrated yet).
    # This is calculated from calibration samples: max(samples) * 1.15
    head_forward_threshold_calibrated: float = 0.0


DEFAULT_SETTINGS = AppSettings()


def get_capture_base_dir() -> Path:
    return Path.home() / "Pictures" / APP_NAME


def get_day_capture_dir(target_day: date) -> Path:
    return get_capture_base_dir() / target_day.isoformat()


def get_database_path() -> Path:
    return Path.home() / ".sitalarm" / "sitalarm.db"

