from __future__ import annotations


APP_STYLESHEET = """
QWidget {
    color: #E7EAF0;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QMainWindow, QWidget#mainRoot {
    background: #101318;
}
QFrame#card {
    background: #171B22;
    border: 1px solid #2A303A;
    border-radius: 10px;
}
QLabel#appTitle {
    font-size: 22pt;
    font-weight: 700;
    color: #F7F9FC;
}
QLabel#appSubtitle, QLabel#mutedText {
    color: #98A2B3;
}
QLabel#sectionTitle {
    font-size: 12pt;
    font-weight: 650;
    color: #F4F6FA;
}
QLabel#fieldLabel {
    color: #B8C0CC;
    font-weight: 600;
}
QLabel#versionBadge {
    background: #202A38;
    color: #74C0FC;
    border: 1px solid #30465F;
    border-radius: 11px;
    padding: 4px 10px;
    font-weight: 700;
}
QLabel#statusBadge {
    border-radius: 10px;
    padding: 4px 10px;
    font-weight: 700;
    background: #27303C;
    color: #C7D0DD;
}
QLabel#statusBadge[state="running"] {
    background: #123B56;
    color: #7DD3FC;
}
QLabel#statusBadge[state="success"] {
    background: #123E2A;
    color: #86EFAC;
}
QLabel#statusBadge[state="error"] {
    background: #4A1D25;
    color: #FDA4AF;
}
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {
    background: #11151B;
    border: 1px solid #303744;
    border-radius: 6px;
    min-height: 22px;
    padding: 5px 9px;
    selection-background-color: #2C7BE5;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {
    border: 1px solid #4DA3FF;
}
QComboBox::drop-down {
    border: 0;
    width: 24px;
}
QPushButton {
    background: #242A34;
    border: 1px solid #343C49;
    border-radius: 7px;
    padding: 8px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background: #2D3541;
}
QPushButton:pressed {
    background: #20262F;
}
QPushButton:disabled {
    color: #6B7280;
    background: #1A1E25;
    border-color: #252B34;
}
QPushButton#primaryButton {
    background: #2F80ED;
    border-color: #4595FF;
    color: white;
}
QPushButton#primaryButton:hover {
    background: #3D8CF4;
}
QPushButton#dangerButton {
    color: #FDA4AF;
}
QCheckBox {
    spacing: 8px;
}
QCheckBox::indicator {
    width: 17px;
    height: 17px;
}
QProgressBar {
    background: #0E1116;
    border: 1px solid #2D3440;
    border-radius: 6px;
    min-height: 12px;
    text-align: center;
    color: #DCE3EC;
}
QProgressBar::chunk {
    background: #2F80ED;
    border-radius: 5px;
}
QPlainTextEdit#logView {
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 9.5pt;
    background: #0B0E12;
    border-radius: 7px;
}
QScrollBar:vertical {
    background: #11151B;
    width: 12px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #3A4351;
    border-radius: 5px;
    min-height: 24px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
"""
