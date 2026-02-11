from __future__ import annotations

from datetime import datetime, timedelta


REMINDER_MESSAGES = {
    "head_forward": "检测到头部前倾，请抬头收下巴，让耳朵与肩膀尽量保持同一直线。",
    "hunchback": "检测到弯腰驼背，请坐直并让背部贴近椅背。",
    "shrugging": "检测到耸肩，请放松肩膀并缓慢下沉。",
    "head_too_close": "检测到你离屏幕过近，请向后坐并保持背部挺直。",
    "screen_time": "连续使用屏幕时间过长，请起身活动 1-2 分钟。",
}


class ReminderPolicy:
    def __init__(self, cooldown_minutes: int) -> None:
        self.cooldown = timedelta(minutes=max(1, cooldown_minutes))
        self._last_sent: dict[str, datetime] = {}

    def should_notify(self, reasons: list[str] | tuple[str, ...], now: datetime) -> bool:
        if not reasons:
            return False

        due = False
        for reason in reasons:
            last = self._last_sent.get(reason)
            if last is None or (now - last) >= self.cooldown:
                due = True

        if due:
            for reason in reasons:
                self._last_sent[reason] = now
        return due

    def build_message(self, reasons: list[str] | tuple[str, ...]) -> str:
        if not reasons:
            return "请保持正确坐姿。"
        parts = [REMINDER_MESSAGES.get(reason, reason) for reason in reasons]
        return "\n".join(parts)
