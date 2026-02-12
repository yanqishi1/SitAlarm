from __future__ import annotations

import json
import platform
import subprocess
from functools import lru_cache


def normalize_compute_device(value: str | None) -> str:
    mode = str(value or "cpu").strip().lower()
    return "gpu" if mode == "gpu" else "cpu"


@lru_cache(maxsize=1)
def gpu_available() -> bool:
    """Return True when the host appears to have a usable GPU adapter.

    This is a capability check for UI/setting purposes. Actual acceleration depends on
    the runtime stack (e.g. OpenCV OpenCL, MediaPipe GPU build).
    """

    system = platform.system().lower()

    # CUDA-capable OpenCV build (rare with opencv-python, common with custom builds).
    if _has_cuda_gpu():
        return True

    if system == "windows":
        return _has_windows_gpu()

    if system == "darwin":
        return _has_macos_gpu()

    if system == "linux":
        return _has_linux_gpu()

    return False


def effective_compute_device(preferred: str | None) -> str:
    device = normalize_compute_device(preferred)
    if device == "gpu" and not gpu_available():
        return "cpu"
    return device


def _has_cuda_gpu() -> bool:
    try:
        import cv2  # type: ignore
    except Exception:
        return False

    cuda_api = getattr(cv2, "cuda", None)
    if cuda_api is None:
        return False

    get_count = getattr(cuda_api, "getCudaEnabledDeviceCount", None)
    if get_count is None:
        return False

    try:
        return int(get_count()) > 0
    except Exception:
        return False


def _has_windows_gpu() -> bool:
    # Avoid importing heavy deps. Use CIM to query video adapters.
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name",
            ],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except Exception:
        return False

    if result.returncode != 0:
        return False

    names = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    if not names:
        return False

    # Filter out the generic fallback adapter.
    for name in names:
        lowered = name.lower()
        if "microsoft basic display" in lowered:
            continue
        return True

    return False


def _has_linux_gpu() -> bool:
    # Best-effort. Many minimal environments won't have lspci.
    try:
        result = subprocess.run(
            ["lspci"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except Exception:
        return False

    if result.returncode != 0:
        return False

    text_out = (result.stdout or "").lower()
    return any(token in text_out for token in ("vga compatible controller", "3d controller", "display controller"))


def _has_macos_gpu() -> bool:
    try:
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except Exception:
        return False

    if result.returncode != 0:
        return False

    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return False

    adapters = payload.get("SPDisplaysDataType", [])
    if not isinstance(adapters, list):
        return False

    for adapter in adapters:
        if not isinstance(adapter, dict):
            continue
        chip_name = str(adapter.get("sppci_model", "")).strip()
        vendor = str(adapter.get("spdisplays_vendor", "")).strip()
        if chip_name or vendor:
            return True
    return False
