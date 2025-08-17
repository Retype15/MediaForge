from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout, 
                             QComboBox, QDialogButtonBox, QLabel, QMessageBox, 
                             QLineEdit, QPushButton, QHBoxLayout, QFileDialog, 
                             QListWidget, QAbstractItemView) # <-- Nuevas
from PyQt6.QtCore import Qt
from src.utils.translator import ts
import os

class SettingsDialog(QDialog):
    # Diccionario de Criterios de Recomendación Disponibles
    RECOMMENDATION_CRITERIA = {
        "quality_desc": "Mejor Calidad (Resolución)",
        "size_desc": "Mayor Tamaño (Más Bitrate)",
        "size_asc": "Menor Tamaño (Ahorrar Espacio)",
        "mtime_desc": "Archivo Más Reciente",
        "mtime_asc": "Archivo Más Antiguo",
    }
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        
        self.setWindowTitle(ts.t('settings_title', 'Settings'))
        self.setMinimumWidth(500)
        self.main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)
        self.general_tab = QWidget()

        self.reco_tab = QWidget()
        reco_layout = QVBoxLayout(self.reco_tab)
        
        reco_label = QLabel("Arrastra los criterios para establecer su prioridad (el de arriba es el más importante).")
        reco_label.setWordWrap(True)
        
        self.reco_list_widget = QListWidget()
        self.reco_list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.reco_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        
        reco_layout.addWidget(reco_label)
        reco_layout.addWidget(self.reco_list_widget)

        self.tabs.addTab(self.reco_tab, "Recomendaciones")

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.main_layout.addWidget(self.button_box)
        self.load_settings()

    def load_settings(self):
        current_lang = self.config.get("general/language", "es_ES")
        self.lang_combo.setCurrentText(current_lang)

        # Cargar ruta FFmpeg
        current_ffmpeg_path = self.config.get("general/ffmpeg_path", "")
        self.ffmpeg_path_input.setText(current_ffmpeg_path)

        self.reco_list_widget.clear()
        # El valor guardado es una lista de IDs, ej: ['quality_desc', 'size_desc']
        saved_order = self.config.get("recommendation/priority_order", list(self.RECOMMENDATION_CRITERIA.keys()))
        
        # Añadir los elementos en el orden guardado
        for key in saved_order:
            if key in self.RECOMMENDATION_CRITERIA:
                self.reco_list_widget.addItem(self.RECOMMENDATION_CRITERIA[key])
                self.reco_list_widget.item(self.reco_list_widget.count() - 1).setData(Qt.ItemDataRole.UserRole, key)

        # Añadir los criterios restantes que no estaban guardados (por si añadimos nuevos)
        for key, text in self.RECOMMENDATION_CRITERIA.items():
            if key not in saved_order:
                self.reco_list_widget.addItem(text)
                self.reco_list_widget.item(self.reco_list_widget.count() - 1).setData(Qt.ItemDataRole.UserRole, key)

    def accept(self):
        # Guardar configuración
        previous_lang = self.config.get("general/language", "es_ES")
        new_lang = self.lang_combo.currentText()
        self.config.set("general/language", new_lang)
        
        # Guardar ruta FFmpeg
        new_ffmpeg_path = self.ffmpeg_path_input.text()
        self.config.set("general/ffmpeg_path", new_ffmpeg_path)

        if previous_lang != new_lang:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText(ts.t('restart_required_body', 'Language change will apply on next start.'))
            msg.setWindowTitle(ts.t('restart_required_title', 'Restart Required'))
            msg.exec()
        
        new_order = []
        for i in range(self.reco_list_widget.count()):
            item = self.reco_list_widget.item(i)
            new_order.append(item.data(Qt.ItemDataRole.UserRole))
        self.config.set("recommendation/priority_order", new_order)

        super().accept()

    def _select_ffmpeg_path(self):
        # Abre un diálogo para seleccionar la carpeta donde está ffmpeg.exe y ffprobe.exe
        # Normalmente es la carpeta 'bin' dentro de la instalación de FFmpeg
        current_path = self.ffmpeg_path_input.text() if self.ffmpeg_path_input.text() else os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(self, ts.t('select_ffmpeg_folder', "Seleccionar Carpeta de FFmpeg Binarios"), current_path)
        if directory:
            self.ffmpeg_path_input.setText(directory)