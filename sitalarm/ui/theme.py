from __future__ import annotations


def build_glass_theme() -> str:
    return """
QMainWindow, QWidget#RootSurface {
    background: #fbf9f3;
    color: #2f3949;
    font-size: 14px;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", sans-serif;
}

QWidget#MainContainer {
    background: #fbf9f3;
}

QStackedWidget#Pages {
    background: transparent;
}

QListWidget#SideNav {
    background: #f2f3f5;
    border: 1px solid #f0d8be;
    border-radius: 14px;
    padding: 12px 8px;
    outline: none;
}

QListWidget#SideNav::item {
    background: transparent;
    border: none;
    margin: 4px 2px;
    min-height: 54px;
}

QScrollArea#PageScrollArea {
    border: none;
    background: transparent;
}

QScrollArea#PageScrollArea QWidget#qt_scrollarea_viewport,
QWidget#PageContent {
    background: transparent;
}

QLabel#PageTitle,
QLabel#StatusTitle {
    font-size: 22px;
    font-weight: 800;
    color: #ff6b00;
}

QLabel#StatusTitle {
    font-size: 26px;
    color: #2f3949;
}

QLabel#SectionTitle {
    font-size: 18px;
    font-weight: 700;
    color: #2f3949;
}

QFrame#UiCard,
QGroupBox#UiCard {
    border: 2px solid #f6c89e;
    border-radius: 26px;
    background: #ffffff;
}

QGroupBox#UiCard {
    margin-top: 0px;
    padding-top: 24px;
}

QGroupBox#UiCard::title {
    left: 24px;
    top: 14px;
    color: #2f3949;
    font-size: 18px;
    font-weight: 800;
}

QFrame#MetricCard {
    border: none;
    background: transparent;
}

QLabel#MetricIcon {
    border-radius: 18px;
    font-size: 16px;
    font-weight: 800;
    color: #ffffff;
    background: #ff8a00;
}

QLabel#MetricIcon[accent="incorrect"] {
    background: #ff2147;
}

QLabel#MetricIcon[accent="unknown"] {
    background: #f4a442;
}

QLabel#MetricName {
    color: #4b5563;
    font-size: 15px;
    font-weight: 600;
}

QLabel#MetricValue {
    color: #ff8a00;
    font-size: 26px;
    font-weight: 800;
}

QLabel#MetricValue[accent="incorrect"] {
    color: #ff2147;
}

QLabel#MetricValue[accent="unknown"] {
    color: #f4a442;
}

QLabel#LastEventLabel {
    font-size: 15px;
    font-weight: 700;
    color: #3d4755;
}

QTextEdit#DashboardMessageBox {
    border: none;
    background: transparent;
    font-size: 16px;
    font-weight: 700;
    color: #3d4755;
    padding: 0;
}

QLabel#SectionHint {
    font-size: 14px;
    color: #637083;
    font-weight: 600;
}

QLabel#FieldLabel {
    font-size: 15px;
    font-weight: 700;
    color: #3d4755;
}

QPushButton {
    min-height: 46px;
    min-width: 120px;
    border-radius: 14px;
    border: 2px solid #f2be88;
    background: #ffffff;
    color: #3d4755;
    padding: 6px 14px;
    font-size: 16px;
    font-weight: 700;
}

QPushButton:hover {
    border-color: #ff8a00;
}

QPushButton#ActionButton {
    background: #ffffff;
    color: #3d4755;
}

QPushButton#PrimaryButton {
    background: #ff6b00;
    border-color: #ff6b00;
    color: #ffffff;
}

QPushButton#PrimaryButton:hover {
    background: #ff7b1f;
    border-color: #ff7b1f;
}

QLineEdit,
QComboBox,
QSpinBox,
QTextEdit {
    border: 2px solid #f3c89c;
    border-radius: 12px;
    background: #ffffff;
    color: #232f3e;
    min-height: 40px;
    padding: 8px 14px;
    font-size: 15px;
    font-weight: 600;
}

QComboBox::drop-down {
    border: none;
    width: 36px;
    background: transparent;
}

QComboBox#WideInput,
QSpinBox#WideInput {
    min-width: 320px;
}

QSpinBox#ShortInput {
    min-width: 90px;
    max-width: 130px;
}

QSpinBox {
    padding-right: 34px;
}

QSpinBox::up-button,
QSpinBox::down-button {
    subcontrol-origin: padding;
    width: 20px;
    border: 1px solid #f3c89c;
    background: #ffffff;
}

QSpinBox::up-button {
    subcontrol-position: top right;
    border-top-right-radius: 10px;
    border-bottom: none;
}

QSpinBox::down-button {
    subcontrol-position: bottom right;
    border-bottom-right-radius: 10px;
}

QSpinBox::up-button:hover,
QSpinBox::down-button:hover {
    background: #fff7ef;
    border-color: #ff8a00;
}

QSpinBox::up-arrow,
QSpinBox::down-arrow {
    width: 9px;
    height: 9px;
}

QCheckBox {
    font-size: 15px;
    font-weight: 700;
    color: #3d4755;
    spacing: 12px;
}

QCheckBox::indicator {
    width: 46px;
    height: 24px;
    border-radius: 12px;
    border: 2px solid #f2be88;
    background: #f2f3f5;
}

QCheckBox::indicator:checked {
    background: #ff6b00;
    border-color: #ff6b00;
}

QLabel#PreviewLabel {
    border-radius: 18px;
    border: 2px solid #f2be88;
    background: #0f172a;
    color: #cbd5e1;
    font-size: 16px;
    font-weight: 600;
}

QLabel#DebugInfoBlock {
    font-size: 15px;
    font-weight: 650;
    color: #3d4755;
    line-height: 1.6;
}

QLabel#InfoDot {
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    border-radius: 14px;
    font-size: 14px;
    font-weight: 800;
    color: #ff6b00;
    border: 2px solid #ff6b00;
    background: #fff7ef;
    qproperty-alignment: AlignCenter;
}

QTableWidget {
    background: #ffffff;
    border: 1px solid #f3d8be;
    border-radius: 14px;
    color: #334155;
    gridline-color: #f3e5d7;
}

QHeaderView::section {
    background: #fdf4e8;
    border: none;
    border-bottom: 1px solid #f3d8be;
    color: #334155;
    font-size: 14px;
    font-weight: 700;
    padding: 6px 8px;
}

QStatusBar {
    background: #ffffff;
    border-top: 1px solid #f3d8be;
    color: #667085;
}

QToolTip {
    border: 1px solid #f2be88;
    border-radius: 8px;
    background: #fff9ef;
    color: #334155;
    padding: 6px 8px;
}

QScrollBar:vertical {
    width: 10px;
    background: transparent;
}

QScrollBar::handle:vertical {
    background: #f2be88;
    border-radius: 5px;
    min-height: 28px;
}

QScrollBar:horizontal {
    height: 10px;
    background: transparent;
}

QScrollBar::handle:horizontal {
    background: #f2be88;
    border-radius: 5px;
    min-width: 28px;
}

QScrollBar::add-line,
QScrollBar::sub-line {
    width: 0;
    height: 0;
}

QMenu {
    background: #ffffff;
    border: 1px solid #f2be88;
    border-radius: 8px;
    padding: 4px;
}

QMenu::item {
    padding: 8px 12px;
    border-radius: 6px;
}

QMenu::item:selected {
    background: #ff6b00;
    color: #ffffff;
}
"""
