import sys, os, json, traceback
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QSplitter,
    QWidget,
    QFileDialog,
    QGridLayout,
    QPushButton,
    QLabel,
    QListWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidgetItem,
    QAbstractItemView,
)
from PyQt6.QtCore import pyqtSignal, QThread, Qt, QUrl
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from pathlib import Path
import multiprocessing

from main import extract_audio, transcribe_audio, cut_clip

CSS = """
/* Global Window & Fonts */
QWidget {
    background-color: #0f172a; 
    color: #f1f5f9;            
    font-family: BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 13px;
}

/* Splitter Styling */
QSplitter::handle {
    background-color: #1e293b;
    margin: 2px;
}
QSplitter::handle:hover {
    background-color: #6366f1; 
}

/* Base Push Buttons */
QPushButton {
    background-color: #1e293b;
    color: #e2e8f0;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #334155;
    border-color: #475569;
}
QPushButton:pressed {
    background-color: #0f172a;
}
QPushButton:disabled {
    background-color: #0f172a;
    color: #475569;
    border-color: #1e293b;
}

/* Primary Transcribe Button (Indigo Accent) */
QPushButton#transcribeBtn {
    background-color: #4f46e5;
    color: #ffffff;
    border: none;
}
QPushButton#transcribeBtn:hover {
    background-color: #6366f1;
}

/* Accent Export Button (Amber/Orange Action) */
QPushButton#exportBtn {
    background-color: #d97706;
    color: #ffffff;
    border: none;
}
QPushButton#exportBtn:hover {
    background-color: #f59e0b;
}

/* Video Player Container Area */
QVideoWidget {
    background-color: #020617;
    border: 1px solid #1e293b;
    border-radius: 8px;
}

/* Transcript List Widget */
QListWidget {
    background-color: #020617;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 6px;
    outline: none;
}

QListWidget::item {
    background-color: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 6px;
    padding: 10px;
    margin-bottom: 6px;
    color: #cbd5e1;
}

QListWidget::item:hover {
    background-color: #1e293b;
    border-color: #334155;
}

/* Selected Clips (Gradient Violet Highlight) */
QListWidget::item:selected {
    background-color: #4338ca;
    border: 1px solid #6366f1;
    color: #ffffff;
}

/* Header Labels */
QLabel#headerLabel {
    font-size: 14px;
    font-weight: 700;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
"""

def setup_crash_logging():
    log_path = Path.home() / "Library" / "Application Support" / "ux-clipper" / "logs" / "crash.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_exception(exc_type, exc_value, exc_tb):
        with open(log_path, "a") as f:
            f.write("---\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)

    sys.excepthook = log_exception

class VideoPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        self.file_picker = FilePicker()
        self.play_button = QPushButton("Play ▶ ")
        self.pause_button = QPushButton("Pause ⏸ ")
        self.video_widget = QVideoWidget()
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()

        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.setAudioOutput(self.audio_output)

        layout.addWidget(self.video_widget, stretch=1)
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)
        controls_layout.addWidget(self.play_button)
        controls_layout.addWidget(self.pause_button)
        controls_layout.addStretch()
        controls_layout.addWidget(self.file_picker)
        layout.addLayout(controls_layout)
        self.play_button.clicked.connect(self.media_player.play)
        self.pause_button.clicked.connect(self.media_player.pause)

        self.setLayout(layout)

    def load_video(self, file_path: str):
        video_path = QUrl.fromLocalFile(file_path)
        self.media_player.setSource(video_path)
        # Play then immediate pause to load the first frame into player, but not autoplay
        self.media_player.play()
        self.media_player.pause()

    def jump_to_timestamp(self, timestamp: float):
        timestamp = int(timestamp)
        self.media_player.setPosition(timestamp)


class FilePicker(QWidget):
    video_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()
        file_browser_btn = QPushButton("Load video")
        file_browser_btn.clicked.connect(self.open_file_dialog)
        layout.addWidget(file_browser_btn)
        self.setLayout(layout)

        layout.addWidget(file_browser_btn)

    def open_file_dialog(self):
        print("File picker opened")
        dialog = QFileDialog(self)
        dialog.setDirectory(r"/Users/antoni/Downloads")
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dialog.setNameFilter("Video Files (*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm)")
        dialog.setViewMode(QFileDialog.ViewMode.Detail)
        if dialog.exec():
            filenames = dialog.selectedFiles()
            if filenames:
                # self.file_list.addItems([str(Path(filename)) for filename in filenames])
                self.video_selected.emit(filenames[0])


class TranscribeWorker(QThread):
    finished = pyqtSignal(str)

    def __init__(self, audio_path):
        super().__init__()
        self.audio_path = audio_path

    def run(self):
        transcript_path = transcribe_audio(self.audio_path)
        self.finished.emit(transcript_path)

class ExportClipWorker(QThread):
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, input_video_path, start_ms, end_ms, clip_title):
        super().__init__()
        self.input_video_path = input_video_path
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.clip_title = clip_title
        # self.transcript_selection = transcript_selection
        #Get first and last timestamp in ms from the list containing the selection

    def run(self):
        try:
            start_val = str(self.start_ms / 1000.0)
            end_val = str(self.end_ms / 1000.0)

            clip_path = cut_clip(
                self.input_video_path, start_val, end_val, self.clip_title
            )
            self.finished.emit(str(clip_path))
        except Exception as e:
            self.failed.emit(str(e))

class TranscriptPanel(QWidget):
    timestamp_requested = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        self.transcribe_button = QPushButton("Transcribe")
        self.export_clip_button = QPushButton("Export clip")
        self.transcribe_button.clicked.connect(self.start_transcription)
        self.export_clip_button.clicked.connect(self.export_clip_from_selection)

        self.transcript_list = QListWidget(self)
        self.transcript_list.setSelectionMode(
        QAbstractItemView.SelectionMode.ContiguousSelection)

        self.transcript_list.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(QLabel("Transcript:"))
        layout.addWidget(self.transcribe_button)
        layout.addWidget(self.export_clip_button)
        layout.addWidget(self.transcript_list)
        self.setLayout(layout)

        self.audio_path = None
        self.video_path = None
        self.worker = None

        self.transcript_list.itemDoubleClicked.connect(
            self.get_timestamp_on_double_click
        )

    def on_video_selected(self, video_path):
        self.audio_path = extract_audio(video_path)
        self.video_path = video_path

    def start_transcription(self):
        if not self.audio_path:
            return
        self.transcribe_button.setEnabled(False)
        self.worker = TranscribeWorker(self.audio_path)
        self.worker.finished.connect(self.on_transcription_done)
        self.worker.start()

    def on_transcription_done(self, transcript_path):
        self.transcribe_button.setEnabled(True)

        with open(transcript_path) as f:
            segments = json.load(f)

        self.transcript_list.clear()

        for segment in segments:
            raw_start = segment["start"]
            raw_end = segment.get("end", raw_start + 2.0)
            timestamp_str = self.format_timestamp(raw_start)

            item = QListWidgetItem(f"[{timestamp_str}] {segment['text']}")

            # Store a dictionary containing start, end, and text
            item.setData(
                Qt.ItemDataRole.UserRole,
                {
                    "start_ms": int(float(raw_start) * 1000),
                    "end_ms": int(float(raw_end) * 1000),
                    "text": segment["text"],
                },
            )
            self.transcript_list.addItem(item)

        self.transcript_list.show()

    def get_timestamp_on_double_click(self, item: QListWidgetItem):
        data = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(data, dict):
            start_ms = data.get("start_ms", 0)
            self.timestamp_requested.emit(float(start_ms))
            print(f"Jumping to {start_ms / 1000.0}s ({start_ms}ms)")

    def _on_selection_changed(self,):
        selected_items = self.transcript_list.selectedItems()
        if len(selected_items) < 2:
            return
        for item in selected_items:
            data = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, dict):
                print(f"Selected: {item.text()} at {data['start_ms'] / 1000.0}s")
    
    def export_clip_from_selection(self):
        selected_items = self.transcript_list.selectedItems()

        if not selected_items or not self.video_path:
            print("Export failed: No selection or video loaded")
            return

        first_data = selected_items[0].data(Qt.ItemDataRole.UserRole)
        last_data = selected_items[-1].data(Qt.ItemDataRole.UserRole)

        if first_data is None or last_data is None:
            print("Export failed: Selected items carry no timestamp data")
            return

        start_ms = first_data["start_ms"]
        end_ms = last_data["end_ms"]

        # Clean the title string safely
        raw_text = first_data.get("text", "clip").strip()[:30]
        clip_title = "".join(
            c for c in raw_text if c.isalnum() or c in (" ", "_", "-")
        ).rstrip()

        self.export_clip_button.setEnabled(False)

        self.export_worker = ExportClipWorker(
            self.video_path, start_ms, end_ms, clip_title
        )
        self.export_worker.finished.connect(self.on_export_done)
        self.export_worker.failed.connect(self.on_export_failed)
        self.export_worker.start()

    def on_export_done(self, clip_path):
        self.export_clip_button.setEnabled(True)
        print(f"Clip exported successfully: {clip_path}")

    def on_export_failed(self, error_msg):
        self.export_clip_button.setEnabled(True)
        print(f"Clip export failed: {error_msg}")

    @staticmethod
    def format_timestamp(seconds):
        minutes, seconds = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        return (
            f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            if hours
            else f"{minutes:02d}:{seconds:02d}"
        )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Main window setup
        self.setWindowTitle("Clipper")
        self.setGeometry(100, 100, 1900, 1060)

        # Set up nested widget references
        transcript_panel = TranscriptPanel()
        video_panel = VideoPanel()

        #Set up signal connections
        video_panel.file_picker.video_selected.connect(video_panel.load_video)
        video_panel.file_picker.video_selected.connect(
            transcript_panel.on_video_selected
        )
        transcript_panel.timestamp_requested.connect(video_panel.jump_to_timestamp)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(video_panel)
        splitter.addWidget(transcript_panel)

        self.setCentralWidget(splitter)
        self.show()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    setup_crash_logging()
    app = QApplication(sys.argv)
    app.setStyleSheet(CSS)
    window = MainWindow()

    primary = app.primaryScreen()
    other_screens = [s for s in app.screens() if s != primary]
    target_screen = other_screens[0] if other_screens else primary

    geometry = target_screen.availableGeometry()

    x = geometry.x() + (geometry.width() - window.width()) // 2
    y = geometry.y() + (geometry.height() - window.height()) // 2
    window.move(x, y)

    sys.exit(app.exec())
