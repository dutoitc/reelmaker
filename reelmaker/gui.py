from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import __version__
from .gui_style import APP_STYLESHEET
from .progress import PROGRESS_PREFIX, default_timing_history_path

try:
    from PySide6.QtCore import QProcess, QProcessEnvironment, QSettings, QTimer, Qt
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QSizePolicy,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:  # pragma: no cover - exercised only without GUI extra
    raise RuntimeError('PySide6 is not installed. Run: pip install -e "[gui]"') from exc


_STAGE_RANGES = {
    "transcription": (0, 33),
    "analysis": (33, 60),
    "scenes": (60, 70),
    "render": (70, 96),
    "export": (96, 100),
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


def _field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("fieldLabel")
    return label


def _make_card(title: str, subtitle: str = "") -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(10)

    heading = QLabel(title)
    heading.setObjectName("sectionTitle")
    layout.addWidget(heading)
    if subtitle:
        description = QLabel(subtitle)
        description.setObjectName("mutedText")
        description.setWordWrap(True)
        layout.addWidget(description)
    return card, layout


class ReelmakerWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Reelmaker")
        self.resize(1080, 920)
        self.setMinimumSize(900, 820)
        self.process: QProcess | None = None
        self.output_buffer = ""
        self.run_started_at: float | None = None
        self.last_eta: float | None = None
        self.settings = QSettings("Reelmaker", "Reelmaker")

        root = QWidget(self)
        root.setObjectName("mainRoot")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        self._build_header(layout)
        self._build_source_card(layout)
        self._build_settings_card(layout)
        self._build_status_card(layout)
        self._build_actions(layout)
        self._build_logs_card(layout)

        geometry = self.settings.value("window_geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._update_clock)

    def _build_header(self, parent: QVBoxLayout) -> None:
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(1)
        title = QLabel("Reelmaker")
        title.setObjectName("appTitle")
        subtitle = QLabel("Des vidéos longues vers des réels prêts à publier et à reprendre dans DaVinci Resolve")
        subtitle.setObjectName("appSubtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles)
        header.addStretch(1)
        version = QLabel(f"v{__version__}")
        version.setObjectName("versionBadge")
        header.addWidget(version, 0, Qt.AlignmentFlag.AlignTop)
        parent.addLayout(header)

    def _build_source_card(self, parent: QVBoxLayout) -> None:
        card, body = _make_card("Source", "Choisis la vidéo originale et le dossier qui recevra les analyses, réels et XML de montage.")
        card.setMinimumHeight(142)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)

        self.video_edit = QLineEdit(str(self.settings.value("video", "")))
        self.video_edit.setPlaceholderText("D:\\Videos\\reportage.mp4")
        browse_video = QPushButton("Choisir…")
        browse_video.clicked.connect(self._choose_video)
        browse_video.setFixedWidth(96)
        grid.addWidget(_field_label("Vidéo MP4"), 0, 0)
        grid.addWidget(self.video_edit, 0, 1)
        grid.addWidget(browse_video, 0, 2)

        default_output = self.settings.value("output", str(Path.cwd() / "output"))
        self.output_edit = QLineEdit(str(default_output))
        browse_output = QPushButton("Choisir…")
        browse_output.clicked.connect(self._choose_output)
        browse_output.setFixedWidth(96)
        grid.addWidget(_field_label("Dossier de sortie"), 1, 0)
        grid.addWidget(self.output_edit, 1, 1)
        grid.addWidget(browse_output, 1, 2)

        body.addLayout(grid)
        parent.addWidget(card)

    def _build_settings_card(self, parent: QVBoxLayout) -> None:
        card, body = _make_card("Réglages", "Le profil Qualité privilégie les propositions éditoriales et montages recomposés.")
        card.setMinimumHeight(225)
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(9)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        self.model_edit = QLineEdit(str(self.settings.value("model", "qwen3:4b")))
        self.model_edit.setToolTip("qwen3:8b donne généralement de meilleurs choix éditoriaux si le temps de traitement est acceptable.")
        grid.addWidget(_field_label("Modèle Ollama"), 0, 0)
        grid.addWidget(self.model_edit, 0, 1)

        self.quality_combo = QComboBox()
        self.quality_combo.addItem("Qualité — candidats + classement IA", "quality")
        self.quality_combo.addItem("Rapide — classement local", "fast")
        saved_quality = str(self.settings.value("editorial_quality", "quality"))
        self.quality_combo.setCurrentIndex(0 if saved_quality == "quality" else 1)
        grid.addWidget(_field_label("Sélection éditoriale"), 0, 2)
        grid.addWidget(self.quality_combo, 0, 3)

        self.target_spin = QSpinBox()
        self.target_spin.setRange(1, 30)
        self.target_spin.setValue(int(self.settings.value("target_count", 6)))
        grid.addWidget(_field_label("Nombre de réels"), 1, 0)
        grid.addWidget(self.target_spin, 1, 1)

        self.crop_combo = QComboBox()
        self.crop_combo.addItems(["scene-smart", "smart", "face", "motion", "center"])
        self.crop_combo.setCurrentText(str(self.settings.value("crop_mode", "scene-smart")))
        grid.addWidget(_field_label("Cadrage"), 1, 2)
        grid.addWidget(self.crop_combo, 1, 3)

        self.composition_combo = QComboBox()
        self.composition_combo.addItem("Hybride — continu ou recomposé", "hybrid")
        self.composition_combo.addItem("Passages continus uniquement", "contiguous")
        saved_composition = str(self.settings.value("composition_mode", "hybrid"))
        self.composition_combo.setCurrentIndex(0 if saved_composition == "hybrid" else 1)
        grid.addWidget(_field_label("Montage éditorial"), 2, 0)
        grid.addWidget(self.composition_combo, 2, 1)

        self.subtitle_combo = QComboBox()
        self.subtitle_combo.addItems(["ollama", "basic", "off"])
        self.subtitle_combo.setCurrentText(str(self.settings.value("subtitle_correction", "ollama")))
        grid.addWidget(_field_label("Correction des sous-titres"), 2, 2)
        grid.addWidget(self.subtitle_combo, 2, 3)

        self.subtitle_position_combo = QComboBox()
        self.subtitle_position_combo.addItem("Automatique — évite le texte existant", "auto")
        self.subtitle_position_combo.addItem("Bas", "bottom")
        self.subtitle_position_combo.addItem("Haut", "top")
        saved_position = str(self.settings.value("subtitle_position", "auto"))
        positions = ["auto", "bottom", "top"]
        self.subtitle_position_combo.setCurrentIndex(positions.index(saved_position) if saved_position in positions else 0)
        grid.addWidget(_field_label("Position des sous-titres"), 3, 0)
        grid.addWidget(self.subtitle_position_combo, 3, 1)

        options = QVBoxLayout()
        options.setSpacing(5)
        self.davinci_checkbox = QCheckBox("Créer les XML DaVinci Resolve")
        saved_davinci = self.settings.value("davinci_xml", True, type=bool)
        self.davinci_checkbox.setChecked(bool(saved_davinci))
        self.davinci_checkbox.setToolTip("Un XML Final Cut Pro 7 par réel, référencé sur la vidéo originale.")
        options.addWidget(self.davinci_checkbox)
        self.force_checkbox = QCheckBox("Recalculer transcription, analyse, plans et corrections")
        options.addWidget(self.force_checkbox)
        grid.addLayout(options, 3, 2, 1, 2)

        body.addLayout(grid)

        timing_label = QLabel("ETA multi-run activée")
        timing_label.setObjectName("mutedText")
        timing_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        timing_label.setToolTip(
            f"Historique local : {default_timing_history_path()}\n"
            "Médiane des secondes par minute de vidéo, bloc Ollama et seconde rendue."
        )
        body.addWidget(timing_label)
        parent.addWidget(card)

    def _build_status_card(self, parent: QVBoxLayout) -> None:
        card, body = _make_card("Traitement")
        card.setMinimumHeight(170)
        status_row = QHBoxLayout()
        self.status_badge = QLabel("Prêt")
        self.status_badge.setObjectName("statusBadge")
        self.status_badge.setProperty("state", "idle")
        status_row.addWidget(self.status_badge)
        self.stage_label = QLabel("En attente d’une vidéo")
        self.stage_label.setWordWrap(True)
        status_row.addWidget(self.stage_label, 1)
        elapsed_title = QLabel("Écoulé")
        elapsed_title.setObjectName("mutedText")
        status_row.addWidget(elapsed_title)
        self.elapsed_label = QLabel("0 s")
        status_row.addWidget(self.elapsed_label)
        eta_title = QLabel("Restant")
        eta_title.setObjectName("mutedText")
        status_row.addWidget(eta_title)
        self.eta_label = QLabel("—")
        status_row.addWidget(self.eta_label)
        body.addLayout(status_row)

        stage_header = QHBoxLayout()
        stage_caption = QLabel("Étape courante")
        stage_caption.setObjectName("mutedText")
        self.stage_percent = QLabel("0 %")
        self.stage_percent.setObjectName("mutedText")
        stage_header.addWidget(stage_caption)
        stage_header.addStretch(1)
        stage_header.addWidget(self.stage_percent)
        body.addLayout(stage_header)
        self.stage_progress = QProgressBar()
        self.stage_progress.setRange(0, 1000)
        self.stage_progress.setValue(0)
        self.stage_progress.setTextVisible(False)
        body.addWidget(self.stage_progress)

        overall_header = QHBoxLayout()
        overall_caption = QLabel("Progression globale")
        overall_caption.setObjectName("mutedText")
        self.overall_percent = QLabel("0 %")
        self.overall_percent.setObjectName("mutedText")
        overall_header.addWidget(overall_caption)
        overall_header.addStretch(1)
        overall_header.addWidget(self.overall_percent)
        body.addLayout(overall_header)
        self.overall_progress = QProgressBar()
        self.overall_progress.setRange(0, 1000)
        self.overall_progress.setValue(0)
        self.overall_progress.setTextVisible(False)
        body.addWidget(self.overall_progress)
        parent.addWidget(card)

    def _build_actions(self, parent: QVBoxLayout) -> None:
        buttons = QHBoxLayout()
        self.start_button = QPushButton("Démarrer")
        self.start_button.setObjectName("primaryButton")
        self.start_button.clicked.connect(self._start)
        buttons.addWidget(self.start_button)
        self.cancel_button = QPushButton("Annuler")
        self.cancel_button.setObjectName("dangerButton")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel)
        buttons.addWidget(self.cancel_button)
        self.open_button = QPushButton("Ouvrir le dossier")
        self.open_button.clicked.connect(self._open_output)
        buttons.addWidget(self.open_button)
        buttons.addStretch(1)
        parent.addLayout(buttons)

    def _build_logs_card(self, parent: QVBoxLayout) -> None:
        card, body = _make_card("Journal")
        card.setMinimumHeight(170)
        header = QHBoxLayout()
        note = QLabel("Sortie détaillée du pipeline local")
        note.setObjectName("mutedText")
        header.addWidget(note)
        header.addStretch(1)
        clear_button = QPushButton("Effacer")
        clear_button.clicked.connect(lambda: self.logs.clear())
        header.addWidget(clear_button)
        body.addLayout(header)

        self.logs = QPlainTextEdit()
        self.logs.setObjectName("logView")
        self.logs.setReadOnly(True)
        self.logs.setMaximumBlockCount(5000)
        self.logs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        body.addWidget(self.logs, 1)
        parent.addWidget(card, 1)

    def _set_status(self, label: str, state: str) -> None:
        self.status_badge.setText(label)
        self.status_badge.setProperty("state", state)
        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)

    def _set_progress_values(self, stage_value: int | None = None, overall_value: int | None = None) -> None:
        if stage_value is not None:
            clamped = max(0, min(1000, stage_value))
            self.stage_progress.setValue(clamped)
            self.stage_percent.setText(f"{round(clamped / 10):d} %")
        if overall_value is not None:
            clamped = max(0, min(1000, overall_value))
            self.overall_progress.setValue(clamped)
            self.overall_percent.setText(f"{round(clamped / 10):d} %")

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
            "--subtitle-position",
            str(self.subtitle_position_combo.currentData()),
            "--progress-json",
        ]
        if self.davinci_checkbox.isChecked():
            command.append("--davinci-xml")
        if self.quality_combo.currentData() == "quality":
            command.extend([
                "--ranking-mode", "ollama",
                "--candidates-per-chunk", "5",
                "--global-composite-count", "3",
            ])
        else:
            command.extend([
                "--ranking-mode", "local",
                "--candidates-per-chunk", "3",
                "--global-composite-count", "0",
            ])
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
        self.settings.setValue("editorial_quality", self.quality_combo.currentData())
        self.settings.setValue("target_count", self.target_spin.value())
        self.settings.setValue("crop_mode", self.crop_combo.currentText())
        self.settings.setValue("composition_mode", self.composition_combo.currentData())
        self.settings.setValue("subtitle_correction", self.subtitle_combo.currentText())
        self.settings.setValue("subtitle_position", self.subtitle_position_combo.currentData())
        self.settings.setValue("davinci_xml", self.davinci_checkbox.isChecked())

        self.logs.clear()
        self.logs.appendPlainText("$ " + sys.executable + " " + " ".join(self._command()))
        self._set_status("En cours", "running")
        self.stage_label.setText("Initialisation")
        self._set_progress_values(0, 0)
        self.elapsed_label.setText("0 s")
        self.eta_label.setText("—")
        self.last_eta = None
        self.run_started_at = time.monotonic()

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
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
            self._set_status("En cours", "running")
            self.stage_label.setText(f"{label} — {message}" if message else label)
            stage_value = max(0, min(1000, int(progress * 1000)))
            start, end = _STAGE_RANGES.get(stage, (0, 100))
            overall = start + (end - start) * progress
            self._set_progress_values(stage_value, int(overall * 10))
        elif event_type == "run_end":
            if event.get("success"):
                self._set_progress_values(1000, 1000)
                self._set_status("Terminé", "success")
                self.stage_label.setText("Traitement terminé")
                self.last_eta = 0.0
            else:
                self._set_status("Échec", "error")
                self.stage_label.setText("Traitement interrompu")
        elif event_type == "run_error":
            self._set_status("Erreur", "error")
            self.stage_label.setText("Une erreur est survenue")
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
        self._set_status("Annulation", "running")
        self.stage_label.setText("Arrêt du traitement…")
        self.process.terminate()
        QTimer.singleShot(3000, self._kill_if_running)

    def _kill_if_running(self) -> None:
        if self.process is not None and self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()

    def _finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        if self.output_buffer:
            self._handle_line(self.output_buffer)
            self.output_buffer = ""
        self.timer.stop()
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        if exit_code == 0:
            self._set_status("Terminé", "success")
            self.stage_label.setText("Traitement terminé")
            self._set_progress_values(1000, 1000)
            self.eta_label.setText("0 s")
        else:
            self._set_status("Échec", "error")
            self.stage_label.setText(f"Traitement échoué · code {exit_code}")
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
        if self.process is not None and self.process.state() != QProcess.ProcessState.NotRunning:
            answer = QMessageBox.question(self, "Traitement en cours", "Arrêter le traitement et fermer ?")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.process.kill()
        self.settings.setValue("window_geometry", self.saveGeometry())
        event.accept()


def main() -> None:
    app = QApplication(sys.argv)
    app.setOrganizationName("Reelmaker")
    app.setApplicationName("Reelmaker")
    app.setApplicationDisplayName("Reelmaker")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)
    window = ReelmakerWindow()
    window.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
