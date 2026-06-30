from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from .progress import PROGRESS_PREFIX, default_timing_history_path

try:
    from PySide6.QtCore import QProcess, QProcessEnvironment, QSettings, QTimer, Qt
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:  # pragma: no cover - exercised only without GUI extra
    raise RuntimeError('PySide6 is not installed. Run: pip install -e ".[gui]"') from exc


_STAGE_RANGES = {
    "transcription": (0, 35),
    "analysis": (35, 62),
    "scenes": (62, 72),
    "render": (72, 100),
}


def _format_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "—"
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d} h {minutes:02d} min"
    if minutes:
        return f"{minutes:d} min {secs:02d} s"
    return f"{secs:d} s"


class ReelmakerWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Reelmaker")
        self.resize(980, 760)
        self.process: QProcess | None = None
        self.output_buffer = ""
        self.run_started_at: float | None = None
        self.last_eta: float | None = None
        self.settings = QSettings("Reelmaker", "Reelmaker")

        root = QWidget(self)
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        form = QFormLayout()
        layout.addLayout(form)

        self.video_edit = QLineEdit(str(self.settings.value("video", "")))
        video_row = QHBoxLayout()
        video_row.addWidget(self.video_edit)
        browse_video = QPushButton("Choisir…")
        browse_video.clicked.connect(self._choose_video)
        video_row.addWidget(browse_video)
        form.addRow("Vidéo MP4", video_row)

        default_output = self.settings.value("output", str(Path.cwd() / "output"))
        self.output_edit = QLineEdit(str(default_output))
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_edit)
        browse_output = QPushButton("Choisir…")
        browse_output.clicked.connect(self._choose_output)
        output_row.addWidget(browse_output)
        form.addRow("Dossier de sortie", output_row)

        self.model_edit = QLineEdit(str(self.settings.value("model", "qwen3:4b")))
        form.addRow("Modèle Ollama", self.model_edit)

        self.target_spin = QSpinBox()
        self.target_spin.setRange(1, 30)
        self.target_spin.setValue(int(self.settings.value("target_count", 6)))
        form.addRow("Nombre de réels", self.target_spin)

        self.crop_combo = QComboBox()
        self.crop_combo.addItems(["scene-smart", "smart", "face", "motion", "center"])
        self.crop_combo.setCurrentText(str(self.settings.value("crop_mode", "scene-smart")))
        form.addRow("Cadrage", self.crop_combo)

        self.composition_combo = QComboBox()
        self.composition_combo.addItem("Hybride — passages continus ou recomposés", "hybrid")
        self.composition_combo.addItem("Passages continus uniquement", "contiguous")
        saved_composition = str(self.settings.value("composition_mode", "hybrid"))
        self.composition_combo.setCurrentIndex(0 if saved_composition == "hybrid" else 1)
        form.addRow("Montage éditorial", self.composition_combo)

        self.subtitle_combo = QComboBox()
        self.subtitle_combo.addItems(["ollama", "basic", "off"])
        self.subtitle_combo.setCurrentText(str(self.settings.value("subtitle_correction", "ollama")))
        form.addRow("Correction des sous-titres", self.subtitle_combo)

        self.force_checkbox = QCheckBox("Recalculer la transcription et l’analyse")
        form.addRow("Cache", self.force_checkbox)

        timing_label = QLabel(str(default_timing_history_path()))
        timing_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        timing_label.setToolTip(
            "Historique local multi-run. Reelmaker mémorise les secondes par minute de vidéo, "
            "par bloc Ollama et par seconde rendue afin d'affiner les estimations."
        )
        form.addRow("Historique des temps", timing_label)

        status_layout = QFormLayout()
        layout.addLayout(status_layout)
        self.stage_label = QLabel("Prêt")
        self.elapsed_label = QLabel("0 s")
        self.eta_label = QLabel("—")
        status_layout.addRow("Étape", self.stage_label)
        status_layout.addRow("Temps écoulé", self.elapsed_label)
        status_layout.addRow("Temps restant estimé (étape)", self.eta_label)

        self.stage_progress = QProgressBar()
        self.stage_progress.setRange(0, 1000)
        self.stage_progress.setValue(0)
        layout.addWidget(self.stage_progress)

        self.overall_progress = QProgressBar()
        self.overall_progress.setRange(0, 1000)
        self.overall_progress.setValue(0)
        self.overall_progress.setFormat("Progression globale : %p%")
        layout.addWidget(self.overall_progress)

        buttons = QHBoxLayout()
        layout.addLayout(buttons)
        self.start_button = QPushButton("Démarrer")
        self.start_button.clicked.connect(self._start)
        buttons.addWidget(self.start_button)
        self.cancel_button = QPushButton("Annuler")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel)
        buttons.addWidget(self.cancel_button)
        self.open_button = QPushButton("Ouvrir le dossier")
        self.open_button.clicked.connect(self._open_output)
        buttons.addWidget(self.open_button)
        buttons.addStretch(1)

        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setMaximumBlockCount(5000)
        layout.addWidget(self.logs, 1)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._update_clock)

    def _choose_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir une vidéo",
            self.video_edit.text() or str(Path.home()),
            "Vidéos (*.mp4 *.mov *.mkv *.webm);;Tous les fichiers (*)",
        )
        if path:
            self.video_edit.setText(path)
            if not self.output_edit.text().strip():
                self.output_edit.setText(str(Path(path).parent / "output" / Path(path).stem))

    def _choose_output(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Choisir le dossier de sortie",
            self.output_edit.text() or str(Path.cwd()),
        )
        if path:
            self.output_edit.setText(path)

    def _command(self) -> list[str]:
        command = [
            "-m",
            "reelmaker",
            "all",
            "--source-video",
            self.video_edit.text().strip(),
            "--output-dir",
            self.output_edit.text().strip(),
            "--model",
            self.model_edit.text().strip() or "qwen3:4b",
            "--target-count",
            str(self.target_spin.value()),
            "--shortlist-count",
            str(max(self.target_spin.value() * 2, 10)),
            "--yes",
            "--crop-mode",
            self.crop_combo.currentText(),
            "--composition-mode",
            str(self.composition_combo.currentData()),
            "--subtitle-correction",
            self.subtitle_combo.currentText(),
            "--progress-json",
        ]
        if self.force_checkbox.isChecked():
            command.extend(["--force-transcription", "--force-ollama", "--force-scene-detection", "--force-subtitle-correction"])
        return command

    def _start(self) -> None:
        video = Path(self.video_edit.text().strip())
        output = Path(self.output_edit.text().strip())
        if not video.is_file():
            QMessageBox.warning(self, "Vidéo manquante", "Choisis un fichier vidéo existant.")
            return
        if not str(output):
            QMessageBox.warning(self, "Dossier manquant", "Choisis un dossier de sortie.")
            return

        output.mkdir(parents=True, exist_ok=True)
        self.settings.setValue("video", str(video))
        self.settings.setValue("output", str(output))
        self.settings.setValue("model", self.model_edit.text().strip())
        self.settings.setValue("target_count", self.target_spin.value())
        self.settings.setValue("crop_mode", self.crop_combo.currentText())
        self.settings.setValue("composition_mode", self.composition_combo.currentData())
        self.settings.setValue("subtitle_correction", self.subtitle_combo.currentText())

        self.logs.clear()
        self.logs.appendPlainText("$ " + sys.executable + " " + " ".join(self._command()))
        self.stage_label.setText("Initialisation")
        self.stage_progress.setValue(0)
        self.overall_progress.setValue(0)
        self.elapsed_label.setText("0 s")
        self.eta_label.setText("—")
        self.last_eta = None
        self.run_started_at = time.monotonic()

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.MergedChannels)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONUNBUFFERED", "1")
        process.setProcessEnvironment(environment)
        process.setProgram(sys.executable)
        process.setArguments(self._command())
        process.setWorkingDirectory(str(Path.cwd()))
        process.readyReadStandardOutput.connect(self._read_output)
        process.finished.connect(self._finished)
        process.errorOccurred.connect(self._process_error)
        self.process = process
        self.output_buffer = ""
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.timer.start()
        process.start()

    def _read_output(self) -> None:
        if self.process is None:
            return
        data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self.output_buffer += data
        while "\n" in self.output_buffer:
            line, self.output_buffer = self.output_buffer.split("\n", 1)
            self._handle_line(line.rstrip("\r"))

    def _handle_line(self, line: str) -> None:
        if line.startswith(PROGRESS_PREFIX):
            try:
                event = json.loads(line[len(PROGRESS_PREFIX) :])
                self._handle_progress(event)
            except Exception:
                self.logs.appendPlainText(line)
            return
        self.logs.appendPlainText(line)
        scrollbar = self.logs.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _handle_progress(self, event: dict) -> None:
        event_type = str(event.get("event") or "")
        stage = str(event.get("stage") or "")
        label = str(event.get("label") or stage or "Traitement")
        progress = float(event.get("progress") or 0.0)
        self.last_eta = float(event["eta_seconds"]) if event.get("eta_seconds") is not None else None
        if event_type in {"stage_start", "stage_progress", "stage_end"}:
            message = str(event.get("message") or "").strip()
            self.stage_label.setText(f"{label} — {message}" if message else label)
            self.stage_progress.setValue(max(0, min(1000, int(progress * 1000))))
            start, end = _STAGE_RANGES.get(stage, (0, 100))
            overall = start + (end - start) * progress
            self.overall_progress.setValue(max(0, min(1000, int(overall * 10))))
        elif event_type == "run_end":
            if event.get("success"):
                self.overall_progress.setValue(1000)
                self.stage_progress.setValue(1000)
                self.stage_label.setText("Terminé")
                self.last_eta = 0.0
            else:
                self.stage_label.setText("Échec")
        elif event_type == "run_error":
            self.stage_label.setText("Erreur")
            message = str(event.get("message") or "")
            if message:
                self.logs.appendPlainText("ERREUR: " + message)
        self.eta_label.setText(_format_duration(self.last_eta))

    def _update_clock(self) -> None:
        if self.run_started_at is None:
            return
        self.elapsed_label.setText(_format_duration(time.monotonic() - self.run_started_at))
        if self.last_eta is not None and self.last_eta > 0:
            self.last_eta = max(0.0, self.last_eta - 1.0)
            self.eta_label.setText(_format_duration(self.last_eta))

    def _cancel(self) -> None:
        if self.process is None:
            return
        self.stage_label.setText("Annulation…")
        self.process.terminate()
        QTimer.singleShot(3000, self._kill_if_running)

    def _kill_if_running(self) -> None:
        if self.process is not None and self.process.state() != QProcess.NotRunning:
            self.process.kill()

    def _finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        if self.output_buffer:
            self._handle_line(self.output_buffer)
            self.output_buffer = ""
        self.timer.stop()
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        if exit_code == 0:
            self.stage_label.setText("Terminé")
            self.overall_progress.setValue(1000)
            self.eta_label.setText("0 s")
        else:
            self.stage_label.setText(f"Échec — code {exit_code}")
            QMessageBox.critical(
                self,
                "Reelmaker",
                "Le traitement a échoué. Consulte les dernières lignes du journal.",
            )
        self.process = None

    def _process_error(self, error: QProcess.ProcessError) -> None:
        self.logs.appendPlainText(f"Erreur de processus: {error}")

    def _open_output(self) -> None:
        path = Path(self.output_edit.text().strip())
        path.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.process is not None and self.process.state() != QProcess.NotRunning:
            answer = QMessageBox.question(self, "Traitement en cours", "Arrêter le traitement et fermer ?")
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self.process.kill()
        event.accept()


def main() -> None:
    app = QApplication(sys.argv)
    window = ReelmakerWindow()
    window.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
