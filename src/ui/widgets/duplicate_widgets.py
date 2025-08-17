from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QFrame, QMessageBox, QMenu)
from PyQt6.QtGui import QFont, QAction, QDesktopServices
from PyQt6.QtCore import Qt, QUrl, pyqtSignal
import pprint
import os
import re

def format_size(size_bytes):
    if size_bytes == 0: return "0B"
    import math
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

def standardize_text(text: str) -> str:
    clean = text.lower()
    clean = re.sub(r'[\(\[].*?[\)\]]', '', clean)
    clean = re.sub(r'season|temporada', 's', clean)
    clean = re.sub(r'episode|episodio', 'e', clean)
    clean = re.sub(r'[\._\-]', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

class FileEntryWidget(QFrame):
    recommendation_changed = pyqtSignal(str)

    def __init__(self, media_file, parent=None):
        super().__init__(parent)
        self.media_file = media_file
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("FileEntryWidget")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        info_layout = QVBoxLayout()
        filename_label = QLabel(media_file.path.name)
        font = filename_label.font(); font.setBold(True); filename_label.setFont(font)
        path_label = QLabel(str(media_file.path.parent))
        path_label.setStyleSheet("color: #aaa;")
        info_layout.addWidget(filename_label)
        info_layout.addWidget(path_label)
        layout.addLayout(info_layout)
        layout.addStretch()

        quality = media_file.parsed_info.get('resolution', 'N/A')
        codec = media_file.parsed_info.get('codec', '')
        metadata_text = f"{quality} | {codec} | {format_size(media_file.size)}"
        metadata_label = QLabel(metadata_text)
        metadata_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(metadata_label)
        layout.addSpacing(15)
        
        self.keep_button = QPushButton("Mantener")
        self.delete_button = QPushButton("Eliminar")
        self.keep_button.setFixedWidth(80)
        self.delete_button.setFixedWidth(80)
        self.keep_button.setCheckable(True)
        self.delete_button.setCheckable(True)
        self.keep_button.clicked.connect(lambda: self.recommendation_changed.emit('KEEP'))
        self.delete_button.clicked.connect(lambda: self.recommendation_changed.emit('DELETE'))
        layout.addWidget(self.keep_button)
        layout.addWidget(self.delete_button)
        layout.addSpacing(10)

        info_button = QPushButton("i")
        info_button.setFixedSize(25, 25)
        info_button.setToolTip("Mostrar metadatos detallados")
        info_button.clicked.connect(self._show_metadata)
        layout.addWidget(info_button)
        
        self.update_style()

    def update_style(self):
        is_keep = self.media_file.recommendation == 'KEEP'
        self.keep_button.setChecked(is_keep)
        self.delete_button.setChecked(not is_keep)

        if is_keep:
            self.setStyleSheet("""
                #FileEntryWidget { background-color: #384838; border: 1px solid #5a785a; border-radius: 3px; }
                #FileEntryWidget:hover { background-color: #4a5c4a; }
                QPushButton:checked { background-color: #6a9c6a; border: 1px solid #8ac88a; }
            """)
        else:
            self.setStyleSheet("""
                #FileEntryWidget { background-color: transparent; border: 1px solid #2c2c2c; border-radius: 3px; }
                #FileEntryWidget QLabel { color: #888; }
                #FileEntryWidget:hover { background-color: #4a4a4a; }
                QPushButton:checked { background-color: #9c6a6a; border: 1px solid #c88a8a; }
            """)
    
    def _open_file(self):
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.media_file.path)))
        except Exception as e:
            print(f"Error al abrir el archivo {self.media_file.path}: {e}")

    def mouseDoubleClickEvent(self, event):
        self._open_file()
        event.accept()

    def contextMenuEvent(self, event):
        context_menu = QMenu(self)
        info_action = QAction("Información Detallada", self)
        info_action.triggered.connect(self._show_metadata)
        open_action = QAction("Abrir Archivo", self)
        open_action.triggered.connect(self._open_file)
        open_folder_action = QAction("Abrir Carpeta Contenedora", self)
        open_folder_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.media_file.path.parent))))
        move_action = QAction("Mover a...", self); move_action.setEnabled(False)
        delete_action = QAction("Eliminar (Enviar a Papelera)", self); delete_action.setEnabled(False)
        
        context_menu.addAction(info_action)
        context_menu.addSeparator()
        context_menu.addAction(open_action); context_menu.addAction(open_folder_action)
        context_menu.addSeparator()
        context_menu.addAction(move_action); context_menu.addAction(delete_action)
        context_menu.exec(event.globalPos())

    def _show_metadata(self):
        parsed_info_str = pprint.pformat(self.media_file.parsed_info, indent=2)
        if self.media_file.metadata_info:
            duration_s = self.media_file.metadata_info.get('duration', 0)
            minutes, seconds = divmod(duration_s, 60)
            formatted_duration = f"{int(minutes):02d}:{int(seconds):02d} ({duration_s:.2f}s)"
            display_metadata = self.media_file.metadata_info.copy()
            display_metadata['duration'] = formatted_duration
            metadata_info_str = pprint.pformat(display_metadata, indent=2)
        else: metadata_info_str = "No se pudieron extraer metadatos."
        full_info = (f"--- Información Parseada del Nombre ---\n{parsed_info_str}\n\n--- Metadatos del Archivo (ffprobe) ---\n{metadata_info_str}")
        msg_box = QMessageBox(self); msg_box.setWindowTitle(f"Metadatos de {self.media_file.path.name}"); msg_box.setText(full_info)
        font = QFont("Courier New", 10); msg_box.setFont(font); msg_box.exec()

class CollapsibleFrame(QFrame):
    ignore_requested = pyqtSignal()

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.is_expanded = True
        self.main_layout = QVBoxLayout(self); self.main_layout.setContentsMargins(0,0,0,0); self.main_layout.setSpacing(2)
        self.header_frame = QFrame(); self.header_frame.setObjectName("CollapsibleHeader")
        self.header_frame.setStyleSheet("#CollapsibleHeader { background-color: #3a3a3a; border-radius: 3px; }")
        header_layout = QHBoxLayout(self.header_frame); header_layout.setContentsMargins(5,5,5,5)
        self.toggle_button = QPushButton("▼"); self.toggle_button.setFixedSize(20, 20)
        self.toggle_button.setStyleSheet("border: none;"); self.toggle_button.clicked.connect(self.toggle)
        self.title_label = QLabel(title)
        self.ignore_button = QPushButton("👁"); self.ignore_button.setFixedSize(20, 20)
        self.ignore_button.setToolTip("Ignorar este grupo en futuros escaneos")
        self.ignore_button.setStyleSheet("border: none; font-size: 14px;")
        self.ignore_button.clicked.connect(lambda: self.ignore_requested.emit())
        
        header_layout.addWidget(self.toggle_button); header_layout.addWidget(self.title_label, stretch=1)
        header_layout.addWidget(self.ignore_button)
        
        self.content_frame = QWidget(); self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(10, 5, 10, 5)
        self.main_layout.addWidget(self.header_frame); self.main_layout.addWidget(self.content_frame)
    
    def toggle(self):
        self.is_expanded = not self.is_expanded; self.content_frame.setVisible(self.is_expanded)
        self.toggle_button.setText("▼" if self.is_expanded else "►")
    def set_expanded(self, expanded):
        self.is_expanded = expanded; self.content_frame.setVisible(self.is_expanded)
        self.toggle_button.setText("▼" if self.is_expanded else "►")

class DuplicateGroupWidget(CollapsibleFrame):
    ignore_episode_requested = pyqtSignal(str)
    
    def __init__(self, duplicate_group, series_id: str, parent=None):
        super().__init__(duplicate_group.display_title, parent)
        self.group = duplicate_group
        self.episode_id = f"{series_id}/{duplicate_group.group_id}"
        self.ignore_requested.connect(lambda: self.ignore_episode_requested.emit(self.episode_id))
        
        self.setFrameShape(QFrame.Shape.StyledPanel); self.setObjectName("DuplicateGroupWidget")
        self.setStyleSheet("#DuplicateGroupWidget { border: 1px solid #444; }")
        font = self.title_label.font(); font.setPointSize(12); font.setBold(True); self.title_label.setFont(font)
        
        for media_file in self.group.files:
            file_widget = FileEntryWidget(media_file)
            file_widget.recommendation_changed.connect(lambda state, mf=media_file: self.handle_recommendation_change(mf, state))
            self.content_layout.addWidget(file_widget)
        self.set_expanded(True)

    def handle_recommendation_change(self, changed_file, new_state: str):
        if new_state == 'KEEP':
            for i in range(self.content_layout.count()):
                file_widget = self.content_layout.itemAt(i).widget()
                if isinstance(file_widget, FileEntryWidget):
                    is_winner = file_widget.media_file is changed_file
                    file_widget.media_file.recommendation = 'KEEP' if is_winner else 'DELETE'
                    file_widget.update_style()

class SeriesGroupWidget(CollapsibleFrame):
    ignore_requested_signal = pyqtSignal(str, str) # key, level

    def __init__(self, series_title, duplicate_groups, parent=None):
        super().__init__(series_title, parent)
        self.series_id = standardize_text(series_title)
        self.ignore_requested.connect(lambda: self.ignore_requested_signal.emit(self.series_id, 'SERIES'))
        
        self.setFrameShape(QFrame.Shape.NoFrame); self.header_frame.setObjectName("SeriesHeader")
        self.header_frame.setStyleSheet("#SeriesHeader { background-color: #2c2c2c; }")
        font = self.title_label.font(); font.setPointSize(16); self.title_label.setFont(font)
        
        for group in sorted(duplicate_groups, key=lambda g: g.group_id):
            episode_widget = DuplicateGroupWidget(group, self.series_id)
            episode_widget.ignore_episode_requested.connect(
                lambda episode_id: self.ignore_requested_signal.emit(episode_id, 'EPISODE')
            )
            self.content_layout.addWidget(episode_widget)
        self.set_expanded(False)