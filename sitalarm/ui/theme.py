from __future__ import annotations


def build_glass_theme() -> str:
    return """
QMainWindow, QWidget#RootSurface {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 rgba(233, 242, 255, 242),
        stop: 0.55 rgba(224, 236, 252, 236),
        stop: 1 rgba(208, 224, 246, 242)
    );
    color: #1f324b;
    font-size: 13px;
}

QTabWidget::pane {
    border: 1px solid rgba(156, 181, 214, 160);
    border-radius: 18px;
    background: rgba(250, 253, 255, 198);
    top: -2px;
}

QTabBar::tab {
    background: rgba(244, 250, 255, 186);
    border: 1px solid rgba(175, 199, 227, 168);
    border-bottom: none;
    padding: 9px 16px;
    margin-right: 5px;
    border-top-left-radius: 11px;
    border-top-right-radius: 11px;
    color: #2d4665;
}

QTabBar::tab:hover {
    background: rgba(255, 255, 255, 220);
}

QTabBar::tab:selected {
    background: rgba(255, 255, 255, 236);
    color: #17314e;
    font-weight: 600;
}

QGroupBox {
    border: 1px solid rgba(162, 187, 218, 156);
    border-radius: 15px;
    margin-top: 14px;
    padding: 15px 12px 11px 12px;
    background: rgba(249, 253, 255, 192);
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 11px;
    top: -4px;
    color: #234263;
    font-weight: 600;
}

QPushButton {
    border: 1px solid rgba(143, 174, 213, 178);
    border-radius: 12px;
    padding: 8px 15px;
    min-height: 16px;
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 rgba(255, 255, 255, 235),
        stop: 1 rgba(227, 238, 253, 224)
    );
    color: #17314e;
    font-weight: 600;
}

QPushButton:hover {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 rgba(255, 255, 255, 255),
        stop: 1 rgba(236, 245, 255, 238)
    );
    border-color: rgba(118, 160, 214, 210);
}

QPushButton:pressed {
    background: rgba(210, 228, 250, 235);
}

QLabel {
    color: #223a56;
}

QTextEdit, QLineEdit, QSpinBox {
    border: 1px solid rgba(152, 181, 216, 162);
    border-radius: 10px;
    padding: 6px;
    background: rgba(255, 255, 255, 224);
    color: #1c324c;
    selection-background-color: rgba(102, 173, 255, 165);
}

QTextEdit {
    background: rgba(255, 255, 255, 230);
}

QCheckBox {
    color: #243d58;
}

QStatusBar {
    background: rgba(245, 251, 255, 196);
    border-top: 1px solid rgba(158, 186, 218, 138);
    color: #1f3551;
}

QToolTip {
    border: 1px solid rgba(92, 125, 166, 180);
    border-radius: 8px;
    background: rgba(28, 41, 62, 236);
    color: #f5f9ff;
    padding: 6px 8px;
}
"""
