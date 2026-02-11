from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from sitalarm.config import AppSettings, get_capture_base_dir
from sitalarm.services.capture_service import CameraCaptureService, CaptureError
from sitalarm.services.file_service import cleanup_old_capture_dirs, ensure_day_capture_dir
from sitalarm.services.head_ratio_detector import (
    CALIBRATION_SAFETY_MARGIN,
    DEFAULT_HEAD_RATIO_THRESHOLD,
    HeadRatioPostureDetector,
)
from sitalarm.services.live_preview_service import LivePreviewService
from sitalarm.services.posture_detector import PostureResult
from sitalarm.services.reminder_service import ReminderPolicy
from sitalarm.services.settings_service import SettingsService
from sitalarm.services.stats_service import DaySummary, StatsService
from sitalarm.services.storage import Storage


class SitAlarmController(QObject):
    state_changed = pyqtSignal(str)
    summary_updated = pyqtSignal(object)
    history_updated = pyqtSignal(object)
    event_logged = pyqtSignal(object)
    reminder_triggered = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    debug_info_updated = pyqtSignal(object)
    live_debug_frame_updated = pyqtSignal(object)
    calibration_required = pyqtSignal(str)
    calibration_status_updated = pyqtSignal(object)

    def __init__(self, storage: Storage, settings_service: SettingsService, stats_service: StatsService) -> None:
        super().__init__()
        self.storage = storage
        self.settings_service = settings_service
        self.stats_service = stats_service

        self.settings = self.settings_service.load()
        self.capture_service = CameraCaptureService()
        self.detector = HeadRatioPostureDetector(
            ratio_threshold=self._effective_head_ratio_threshold(self.settings.head_ratio_threshold)
        )
        self.reminder_policy = ReminderPolicy(self.settings.reminder_cooldown_minutes)

        self.capture_base_dir = get_capture_base_dir()
        self.capture_base_dir.mkdir(parents=True, exist_ok=True)

        self._paused = False
        self._screen_start = datetime.now()
        self._required_calibration_samples = 2
        self._calibration_ratios: list[float] = []

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.run_detection_now)

        self._live_preview_service = LivePreviewService(camera_index=self.capture_service.camera_index)
        self._live_preview_timer = QTimer(self)
        self._live_preview_timer.setInterval(150)
        self._live_preview_timer.timeout.connect(self._push_live_debug_frame)

    def start(self) -> None:
        self.apply_settings(self.settings)
        self._publish_stats()
        if self._is_calibrated():
            self.state_changed.emit("检测中")
        else:
            self.state_changed.emit("待校准")
            self._emit_calibration_required()

    def stop(self) -> None:
        self._timer.stop()
        self.stop_live_debug()
        self.state_changed.emit("已停止")

    def pause_detection(self) -> None:
        self._paused = True
        self._timer.stop()
        self.state_changed.emit("已暂停")

    def resume_detection(self) -> None:
        if not self._ensure_calibrated_for_detection():
            return

        self._paused = False
        self._timer.start(self.settings.capture_interval_minutes * 60 * 1000)
        self.state_changed.emit("检测中")

    def start_live_debug(self) -> None:
        if self._live_preview_service.started:
            return

        try:
            self._live_preview_service.start()
        except CaptureError as exc:
            self.error_occurred.emit(str(exc))
            return

        self._live_preview_timer.start()

    def stop_live_debug(self) -> None:
        self._live_preview_timer.stop()
        self._live_preview_service.stop()

    def update_settings(self, **changes: object) -> AppSettings:
        self.settings = self.settings_service.update(**changes)
        self.apply_settings(self.settings)
        return self.settings

    def apply_settings(self, settings: AppSettings) -> None:
        self.settings = settings
        self.reminder_policy = ReminderPolicy(settings.reminder_cooldown_minutes)
        self.detector.ratio_threshold = self._effective_head_ratio_threshold(settings.head_ratio_threshold)
        cleanup_old_capture_dirs(self.capture_base_dir, settings.retention_days, datetime.now().date())

        self._timer.stop()
        if self._paused:
            self._emit_calibration_status(phase="paused", message="检测已暂停。")
            return

        if not self._is_calibrated():
            self.state_changed.emit("待校准")
            self._emit_calibration_status(
                phase="required",
                message="请先在设置页拍摄 2 张正确坐姿照片完成校准。",
            )
            return

        self._timer.start(settings.capture_interval_minutes * 60 * 1000)
        self._emit_calibration_status(phase="ready", message="头占比阈值已完成校准。")

    def run_detection_now(self) -> None:
        if self._paused:
            return
        if not self._ensure_calibrated_for_detection():
            return

        now = datetime.now()
        day_dir = ensure_day_capture_dir(self.capture_base_dir, now.date())
        image_path = day_dir / f"{now.strftime('%H%M%S')}.jpg"

        try:
            frame = self._capture_frame_for_detection()
            self.capture_service.save_frame(frame, image_path)
        except CaptureError as exc:
            self.error_occurred.emit(str(exc))
            return

        result = self._detect_posture(frame)
        self._emit_debug_info(now=now, image_path=image_path, frame=frame, result=result, source="scheduled")
        self._record_event(now, image_path, result)
        self._publish_stats()
        self._trigger_reminders(now, result)

    def run_debug_capture(self) -> None:
        now = datetime.now()
        day_dir = ensure_day_capture_dir(self.capture_base_dir, now.date())
        image_path = day_dir / f"debug_{now.strftime('%H%M%S')}.jpg"

        try:
            frame = self._capture_frame_for_detection()
            self.capture_service.save_frame(frame, image_path)
        except CaptureError as exc:
            self.error_occurred.emit(str(exc))
            return

        result = self._detect_posture(frame)
        self._emit_debug_info(now=now, image_path=image_path, frame=frame, result=result, source="manual")

    def capture_head_ratio_calibration_sample(self) -> None:
        now = datetime.now()
        sample_index = len(self._calibration_ratios) + 1
        day_dir = ensure_day_capture_dir(self.capture_base_dir, now.date())
        image_path = day_dir / f"calib_correct_{sample_index}_{now.strftime('%H%M%S')}.jpg"

        try:
            frame = self._capture_frame_for_detection()
            self.capture_service.save_frame(frame, image_path)
        except CaptureError as exc:
            self.error_occurred.emit(str(exc))
            self._emit_calibration_status(phase="error", message=str(exc))
            return

        ratio_result = self.detector.evaluate_frame(frame)
        if ratio_result.head_ratio is None:
            self.error_occurred.emit("未识别到头部，请调整光线或角度后重试。")
            self._emit_calibration_status(
                phase="error",
                message=f"第 {sample_index}/2 张未识别到头部，请保持正对摄像头并重拍。",
            )
            return

        self._calibration_ratios.append(ratio_result.head_ratio)
        captured_count = len(self._calibration_ratios)
        if captured_count < self._required_calibration_samples:
            self._emit_calibration_status(
                phase="partial",
                message=f"已完成第 {captured_count}/2 张，请保持正确坐姿再拍第 2 张。",
            )
            return

        threshold = HeadRatioPostureDetector.recommend_threshold(
            self._calibration_ratios,
            safety_margin=CALIBRATION_SAFETY_MARGIN,
        )
        rounded_threshold = round(threshold, 4)
        self.update_settings(head_ratio_threshold=rounded_threshold)
        self._calibration_ratios.clear()

        self.state_changed.emit("检测中")
        self._emit_calibration_status(
            phase="completed",
            message=f"校准完成，当前头占比阈值：{rounded_threshold:.4f}",
        )

    def reset_head_ratio_calibration(self) -> None:
        self._calibration_ratios.clear()
        self.update_settings(head_ratio_threshold=0.0)
        self._emit_calibration_required()

    def open_today_capture_dir(self) -> Path:
        return ensure_day_capture_dir(self.capture_base_dir, datetime.now().date())

    def _capture_frame_for_detection(self) -> object:
        if self._live_preview_service.started:
            try:
                return self._live_preview_service.read_frame()
            except CaptureError:
                pass
        return self.capture_service.capture_frame()

    def _push_live_debug_frame(self) -> None:
        if not self._live_preview_service.started:
            return

        try:
            frame = self._live_preview_service.read_frame()
        except CaptureError as exc:
            self.stop_live_debug()
            self.error_occurred.emit(str(exc))
            return

        result = self._detect_posture(frame)
        payload = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "frame": frame,
            "status": result.status,
            "reasons": list(result.reasons),
            "confidence": result.confidence,
            "source": "live",
            "brightness": round(self.capture_service.frame_brightness(frame), 2),
            "debug_info": result.debug_info or {},
        }
        self.live_debug_frame_updated.emit(payload)

    def _detect_posture(self, frame: object) -> PostureResult:
        ratio_result = self.detector.evaluate_frame(frame)

        if ratio_result.status == "incorrect":
            reasons = ("head_too_close",)
        else:
            reasons = ()

        debug_info = {
            "head_ratio": round(ratio_result.head_ratio, 4) if ratio_result.head_ratio is not None else None,
            "threshold_head_ratio": round(self.detector.ratio_threshold, 4),
            "face_box": ratio_result.face_box,
            "calibrated": self._is_calibrated(),
        }

        return PostureResult(
            status=ratio_result.status,
            reasons=reasons,
            confidence=ratio_result.head_ratio,
            debug_info=debug_info,
        )

    def _record_event(self, now: datetime, image_path: Path, result: PostureResult) -> None:
        self.storage.insert_posture_event(
            captured_at=now,
            status=result.status,
            reasons=result.reasons,
            image_path=image_path,
            confidence=result.confidence,
        )
        self.stats_service.record_detection(
            day=now.date(),
            status=result.status,
            interval_minutes=self.settings.capture_interval_minutes,
        )

        payload = {
            "time": now.strftime("%H:%M:%S"),
            "status": result.status,
            "reasons": ", ".join(result.reasons) if result.reasons else "-",
            "image_path": str(image_path),
            "confidence": result.confidence,
        }
        self.event_logged.emit(payload)

    def _publish_stats(self) -> None:
        today = datetime.now().date()
        summary: DaySummary = self.stats_service.get_day_summary(today)
        history = self.stats_service.get_last_days(days=7, today=today)
        self.summary_updated.emit(summary)
        self.history_updated.emit(history)

    def _trigger_reminders(self, now: datetime, result: PostureResult) -> None:
        if result.status == "incorrect" and self.reminder_policy.should_notify(result.reasons, now):
            message = self.reminder_policy.build_message(result.reasons)
            self.reminder_triggered.emit(message)

        if not self.settings.screen_time_enabled:
            return

        elapsed_minutes = (now - self._screen_start).total_seconds() / 60.0
        if elapsed_minutes < self.settings.screen_time_threshold_minutes:
            return

        if self.reminder_policy.should_notify(["screen_time"], now):
            self.reminder_triggered.emit(self.reminder_policy.build_message(["screen_time"]))
            self._screen_start = now

    def settings_as_dict(self) -> dict[str, object]:
        return asdict(self.settings)

    def _emit_debug_info(
        self,
        now: datetime,
        image_path: Path,
        frame: object,
        result: PostureResult,
        source: str,
    ) -> None:
        debug_info = result.debug_info or {}
        payload = {
            "time": now.strftime("%H:%M:%S"),
            "image_path": str(image_path),
            "status": result.status,
            "reasons": list(result.reasons),
            "confidence": result.confidence,
            "source": source,
            "brightness": round(self.capture_service.frame_brightness(frame), 2),
            "debug_info": debug_info,
        }
        self.debug_info_updated.emit(payload)

    def _is_calibrated(self) -> bool:
        return self.settings.head_ratio_threshold > 0.0

    def _effective_head_ratio_threshold(self, threshold: float) -> float:
        if threshold > 0.0:
            return threshold
        return DEFAULT_HEAD_RATIO_THRESHOLD

    def _ensure_calibrated_for_detection(self) -> bool:
        if self._is_calibrated():
            return True

        self.state_changed.emit("待校准")
        self.error_occurred.emit("请先在设置页完成头占比校准（拍摄 2 张正确坐姿照片）。")
        self._emit_calibration_required()
        return False

    def _emit_calibration_required(self) -> None:
        message = "首次使用请先校准：在设置页拍 2 张正确坐姿照片，系统会自动计算阈值。"
        self.calibration_required.emit(message)
        self._emit_calibration_status(
            phase="required",
            message="请在设置页拍摄 2 张正确坐姿照片完成校准。",
        )

    def _emit_calibration_status(self, phase: str, message: str) -> None:
        payload = {
            "phase": phase,
            "message": message,
            "captured": len(self._calibration_ratios),
            "required": self._required_calibration_samples,
            "threshold": self.settings.head_ratio_threshold,
        }
        self.calibration_status_updated.emit(payload)
