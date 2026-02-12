from __future__ import annotations

import os
from pathlib import Path
from urllib.request import urlretrieve


# MediaPipe Tasks model hosting (public).
POSE_LANDMARKER_LITE_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
)
FACE_DETECTOR_SHORT_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
)


def get_models_dir() -> Path:
    # Allow override for power users / packaging.
    override = os.environ.get("SITALARM_MODELS_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".sitalarm" / "models"


def ensure_pose_landmarker_model() -> Path:
    return _ensure_model_file(
        relative_path=Path("mediapipe") / "pose_landmarker_lite.task",
        url=POSE_LANDMARKER_LITE_URL,
    )


def ensure_face_detector_model() -> Path:
    return _ensure_model_file(
        relative_path=Path("mediapipe") / "blaze_face_short_range.tflite",
        url=FACE_DETECTOR_SHORT_URL,
    )


def _ensure_model_file(*, relative_path: Path, url: str) -> Path:
    target = get_models_dir() / relative_path
    if target.exists() and target.stat().st_size > 0:
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")

    # urlretrieve is stdlib, no extra deps.
    urlretrieve(url, tmp)  # nosec - controlled URLs

    # Atomic-ish replace on Windows.
    if target.exists():
        target.unlink()
    tmp.replace(target)
    return target
