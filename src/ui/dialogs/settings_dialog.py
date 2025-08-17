from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout, 
                             QComboBox, QDialogButtonBox, QLabel, QMessageBox, 
                             QLineEdit, QPushButton, QHBoxLayout, QFileDialog, 
                             QListWidget, QAbstractItemView, QListWidgetItem)
from PyQt6.QtCore import Qt
from src.utils.translator import ts
from src.core.cache_manager import CacheManager
import os

class SettingsDialog(QDialog):
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
        self.cache = CacheManager()
        
        self.setWindowTitle(ts.t('settings_title', 'Settings'))
        self.setMinimumWidth(500)
        
        self.main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)
        
        # Pestaña General
        self.general_tab = QWidget()
        self.general_layout = QFormLayout(self.general_tab)
        
        self.lang_combo = QComboBox() # Ahora existe
        self.lang_combo.addItems(["es_ES", "en_US"])
        self.general_layout.addRow(ts.t('label_language', 'Language:'), self.lang_combo)

        self.ffmpeg_path_input = QLineEdit()
        self.ffmpeg_path_button = QPushButton("...")
        self.ffmpeg_path_button.setFixedWidth(30)
        ffmpeg_layout = QHBoxLayout()
        ffmpeg_layout.addWidget(self.ffmpeg_path_input)
        ffmpeg_layout.addWidget(self.ffmpeg_path_button)
        self.general_layout.addRow(ts.t('label_ffmpeg_path', 'Ruta FFmpeg:'), ffmpeg_layout)
        self.ffmpeg_path_button.clicked.connect(self._select_ffmpeg_path)
        self.tabs.addTab(self.general_tab, ts.t('tab_general', 'General'))

        # Pestaña de Recomendaciones
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

        # Botones
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.main_layout.addWidget(self.button_box)

        # Seccion de ignorados  
        self.ignore_tab = QWidget()
        ignore_layout = QVBoxLayout(self.ignore_tab)
        
        ignore_label = QLabel("Aquí puedes ver y eliminar elementos de tu lista de ignorados.")
        self.ignore_list_widget = QListWidget()
        
        self.remove_ignore_button = QPushButton("Eliminar Seleccionado de la Lista")
        self.remove_ignore_button.clicked.connect(self._remove_from_ignore_list)
        
        ignore_layout.addWidget(ignore_label)
        ignore_layout.addWidget(self.ignore_list_widget)
        ignore_layout.addWidget(self.remove_ignore_button)

        self.tabs.addTab(self.ignore_tab, "Lista de Ignorados")

        self.load_settings() # Llamar a load_settings DESPUÉS de crear los widgets

    # ... (el resto de la clase se mantiene sin cambios)
    def load_settings(self):
        current_lang = self.config.get("general/language", "es_ES")
        self.lang_combo.setCurrentText(current_lang)
        current_ffmpeg_path = self.config.get("general/ffmpeg_path", "")
        self.ffmpeg_path_input.setText(current_ffmpeg_path)
        self.reco_list_widget.clear()
        saved_order = self.config.get("recommendation/priority_order", list(self.RECOMMENDATION_CRITERIA.keys()))
        for key in saved_order:
            if key in self.RECOMMENDATION_CRITERIA:
                self.reco_list_widget.addItem(self.RECOMMENDATION_CRITERIA[key])
                self.reco_list_widget.item(self.reco_list_widget.count() - 1).setData(Qt.ItemDataRole.UserRole, key)
        for key, text in self.RECOMMENDATION_CRITERIA.items():
            if key not in saved_order:
                self.reco_list_widget.addItem(text)
                self.reco_list_widget.item(self.reco_list_widget.count() - 1).setData(Qt.ItemDataRole.UserRole, key)
        
        self.ignore_list_widget.clear()
        ignored_items = self.cache.get_full_ignore_list()
        for item_data in ignored_items:
            # Crear un item de lista con texto formateado
            display_text = f"[{item_data['level']}] {item_data['key']}"
            item = QListWidgetItem(display_text)
            # Guardar la clave real en los datos del item
            item.setData(Qt.ItemDataRole.UserRole, item_data['key'])
            self.ignore_list_widget.addItem(item)

    def _remove_from_ignore_list(self):
        selected_items = self.ignore_list_widget.selectedItems()
        if not selected_items:
            return
            
        item = selected_items[0]
        key_to_remove = item.data(Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(self, "Confirmar Eliminación",
                                     f"¿Estás seguro de que quieres dejar de ignorar '{key_to_remove}'?")
        
        if reply == QMessageBox.StandardButton.Yes:
            self.cache.remove_from_ignore_list(key_to_remove)
            # Refrescar la lista en la UI
            self.ignore_list_widget.takeItem(self.ignore_list_widget.row(item))

    def closeEvent(self, event):
        # Asegurarse de cerrar la conexión a la base de datos
        self.cache.close()
        super().closeEvent(event)

    def accept(self):
        previous_lang = self.config.get("general/language", "es_ES")
        new_lang = self.lang_combo.currentText()
        self.config.set("general/language", new_lang)
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
        current_path = self.ffmpeg_path_input.text() if self.ffmpeg_path_input.text() else os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(self, ts.t('select_ffmpeg_folder', "Seleccionar Carpeta de FFmpeg Binarios"), current_path)
        if directory:
            self.ffmpeg_path_input.setText(directory)