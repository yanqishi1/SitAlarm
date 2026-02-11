from __future__ import annotations


def build_glass_theme() -> str:
    return """
/* Root window - light modern (like screenshot) */
QMainWindow, QWidget#RootSurface {
    background: rgba(246, 247, 251, 255);
    color: rgba(17, 24, 39, 235);
    font-size: 13px;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", sans-serif;
}

/* Page titles */
QLabel#PageTitle {
    font-size: 22px;
    font-weight: 800;
    color: rgba(17, 24, 39, 240);
    margin-top: 6px;
}

QLabel#PageSubtitle {
    font-size: 12px;
    color: rgba(107, 114, 128, 220);
    margin-bottom: 10px;
}

QLabel#SectionHint {
    color: rgba(107, 114, 128, 220);
    margin-bottom: 6px;
}

/* Left sidebar navigation */
QListWidget#SideNav {
    background: rgba(255, 255, 255, 220);
    border: 1px solid rgba(17, 24, 39, 14);
    border-radius: 18px;
    padding: 10px 8px;
    outline: none;
}

QListWidget#SideNav::item {
    background: transparent;
    border: none;
    margin: 6px 2px;
    border-radius: 14px;
    min-height: 54px;
}

QListWidget#SideNav::item:hover {
    background: rgba(245, 158, 11, 28);
}

QListWidget#SideNav::item:selected {
    background: rgba(245, 158, 11, 235);
}

QListWidget#SideNav::item:selected:active {
    background: rgba(245, 158, 11, 235);
}

/* Scroll areas for pages */
QScrollArea#PageScrollArea {
    border: none;
    background: transparent;
}

QScrollArea#PageScrollArea QWidget#qt_scrollarea_viewport {
    background: transparent;
}

/* Group box - card */
QGroupBox {
    border: 1px solid rgba(17, 24, 39, 10);
    border-radius: 18px;
    margin-top: 14px;
    /* Extra top padding so title never overlaps content */
    padding: 28px 14px 14px 14px;
    background: rgba(255, 255, 255, 240);
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    top: 8px;
    color: rgba(17, 24, 39, 220);
    font-weight: 800;
    font-size: 13px;
}

/* Buttons */
QPushButton {
    border: 1px solid rgba(17, 24, 39, 16);
    border-radius: 12px;
    padding: 9px 14px;
    min-height: 16px;
    background: rgba(255, 255, 255, 235);
    color: rgba(17, 24, 39, 230);
    font-weight: 700;
}

QPushButton:hover {
    background: rgba(255, 255, 255, 255);
    border-color: rgba(245, 158, 11, 150);
}

QPushButton:pressed {
    background: rgba(249, 250, 251, 255);
}

QPushButton#PrimaryButton {
    background: rgba(245, 158, 11, 235);
    border-color: rgba(245, 158, 11, 235);
    color: rgba(255, 255, 255, 255);
}

QPushButton#PrimaryButton:hover {
    background: rgba(245, 158, 11, 255);
    border-color: rgba(245, 158, 11, 255);
}

QPushButton#SecondaryButton {
    background: rgba(255, 255, 255, 235);
    color: rgba(17, 24, 39, 230);
}

/* Labels */
QLabel {
    color: rgba(17, 24, 39, 235);
}

/* Inputs */
QTextEdit, QLineEdit, QSpinBox, QComboBox {
    border: 1px solid rgba(17, 24, 39, 14);
    border-radius: 12px;
    padding: 7px 10px;
    background: rgba(255, 255, 255, 245);
    color: rgba(17, 24, 39, 235);
    selection-background-color: rgba(245, 158, 11, 80);
}

/* Reserve space for spin buttons / combo arrow to avoid text overlap */
QSpinBox {
    padding-right: 36px;
}

QComboBox {
    padding-right: 34px;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border-left: 1px solid rgba(17, 24, 39, 10);
    border-top-right-radius: 12px;
    border-bottom-right-radius: 12px;
    background: transparent;
}

QComboBox::down-arrow {
    width: 12px;
    height: 12px;
}

QTextEdit:focus, QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: rgba(245, 158, 11, 180);
    border-width: 2px;
}

/* Tables - glass list */
QTableWidget {
    background: rgba(255, 255, 255, 150);
    border: 1px solid rgba(15, 23, 42, 14);
    border-radius: 12px;
    gridline-color: rgba(15, 23, 42, 10);
    color: rgba(15, 23, 42, 220);
    selection-background-color: rgba(6, 182, 212, 60);
    selection-color: rgba(15, 23, 42, 230);
}

QHeaderView::section {
    background: rgba(255, 255, 255, 190);
    border: none;
    border-bottom: 1px solid rgba(15, 23, 42, 12);
    padding: 8px 10px;
    font-weight: 800;
    color: rgba(15, 23, 42, 180);
}

QTableWidget::item {
    padding: 6px 8px;
}

QTableWidget::item:selected {
    background: rgba(59, 130, 246, 70);
}

/* Checkbox - modern style */
QCheckBox {
    color: rgba(17, 24, 39, 235);
    spacing: 8px;
}

QCheckBox::indicator {
    width: 42px;
    height: 24px;
    border-radius: 12px;
    border: 1px solid rgba(17, 24, 39, 16);
    background: rgba(229, 231, 235, 255);
}

QCheckBox::indicator:checked {
    background: rgba(245, 158, 11, 235);
    border-color: rgba(245, 158, 11, 235);
}

/* Status bar - subtle glass */
QStatusBar {
    background: rgba(255, 255, 255, 230);
    border-top: 1px solid rgba(17, 24, 39, 10);
    color: rgba(107, 114, 128, 230);
    font-size: 11px;
    padding: 4px;
}

/* Tooltip */
QToolTip {
    border: 1px solid rgba(15, 23, 42, 20);
    border-radius: 8px;
    background: rgba(255, 255, 255, 235);
    color: rgba(15, 23, 42, 220);
    padding: 6px 10px;
    font-size: 12px;
}

/* Scrollbar styling - minimal light */
QScrollBar:vertical {
    background: rgba(15, 23, 42, 10);
    width: 12px;
    border-radius: 6px;
    margin: 2px;
}

QScrollBar::handle:vertical {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 rgba(6, 182, 212, 160),
        stop: 1 rgba(59, 130, 246, 160)
    );
    border-radius: 6px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 rgba(6, 182, 212, 210),
        stop: 1 rgba(59, 130, 246, 210)
    );
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background: rgba(15, 23, 42, 10);
    height: 12px;
    border-radius: 6px;
    margin: 2px;
}

QScrollBar::handle:horizontal {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 rgba(6, 182, 212, 160),
        stop: 1 rgba(59, 130, 246, 160)
    );
    border-radius: 6px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 rgba(6, 182, 212, 210),
        stop: 1 rgba(59, 130, 246, 210)
    );
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* Menu styling for tray - light glass */
QMenu {
    background: rgba(255, 255, 255, 240);
    border: 1px solid rgba(15, 23, 42, 18);
    border-radius: 10px;
    padding: 6px;
}

QMenu::item {
    padding: 8px 24px 8px 14px;
    border-radius: 6px;
    color: rgba(15, 23, 42, 230);
    font-weight: 600;
}

QMenu::item:selected {
    background: rgba(245, 158, 11, 235);
    color: #ffffff;
}

QMenu::separator {
    height: 1px;
    background: rgba(15, 23, 42, 12);
    margin: 6px 10px;
}

/* SpinBox buttons */
QSpinBox::up-button, QSpinBox::down-button {
    subcontrol-origin: border;
    width: 22px;
    border: none;
    background: rgba(17, 24, 39, 6);
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background: rgba(245, 158, 11, 40);
}

QSpinBox::up-button {
    subcontrol-position: top right;
    border-top-right-radius: 8px;
}

QSpinBox::down-button {
    subcontrol-position: bottom right;
    border-bottom-right-radius: 8px;
}
"""
