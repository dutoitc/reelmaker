import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from reelmaker.gui import ReelmakerWindow


def test_gui_builds_quality_oriented_cli_command(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ReelmakerWindow()
    window.video_edit.setText(str(tmp_path / "source.mp4"))
    window.output_edit.setText(str(tmp_path / "output"))

    command = window._command()

    assert "--progress-json" in command
    assert "--davinci-xml" in command
    assert command[command.index("--composition-mode") + 1] == "hybrid"
    assert command[command.index("--subtitle-correction") + 1] == "ollama"
    assert command[command.index("--crop-mode") + 1] == "scene-smart"
    window.close()
    if app.applicationName() == "":
        app.quit()


def test_gui_can_disable_davinci_xml(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ReelmakerWindow()
    window.video_edit.setText(str(tmp_path / "source.mp4"))
    window.output_edit.setText(str(tmp_path / "output"))
    window.davinci_checkbox.setChecked(False)

    assert "--davinci-xml" not in window._command()
    window.close()
    if app.applicationName() == "":
        app.quit()
