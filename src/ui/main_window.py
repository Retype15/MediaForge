from PyQt6.QtWidgets import (QMainWindow, QVBoxLayout, QWidget, QPushButton, QProgressBar,
                             QStatusBar, QHBoxLayout, QFileDialog, QMessageBox, QScrollArea,
                             QFrame, QToolBar, QLabel)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt

from src.utils.translator import ts
from src.core.workers import ScanWorker, standardize_text
from src.ui.dialogs.settings_dialog import SettingsDialog
from src.modules.scanners.default_scanner import DefaultScanner
from src.modules.matchers.media_name_matcher import MediaNameMatcher
from src.ui.widgets.path_widgets import SidePanel, PathEntryWidget
from src.ui.widgets.duplicate_widgets import (SeriesGroupWidget, DuplicateGroupWidget, 
                                              FileEntryWidget)
from src.ui.dialogs.action_confirm_dialog import ActionConfirmDialog, ConfirmDialog
from src.core.action_worker import ActionWorker

class MainWindow(QMainWindow):
    def __init__(self, config_manager, cache_manager):
        super().__init__()
        self.config = config_manager
        self.cache = cache_manager
        self.worker = None
        self.action_worker = None
        self.result_widgets = {}

        self.setWindowTitle(ts.t('app_title', 'MediaForge'))
        self.setGeometry(100, 100, 1280, 720)

        self._create_actions_and_menus()
        self._create_ui()

    def _create_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QHBoxLayout(self.central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.side_panel = SidePanel()
        main_layout.addWidget(self.side_panel)
        self.side_panel.add_path_requested.connect(self._add_new_path_to_active)

        results_widget = QWidget()
        results_main_layout = QVBoxLayout(results_widget)
        
        self.scan_button = QPushButton(ts.t('scan_selected_paths', 'Escanear Rutas Seleccionadas'))
        self.scan_button.clicked.connect(self._toggle_scan)
        results_main_layout.addWidget(self.scan_button)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(10, 10, 10, 10)
        self.results_layout.setSpacing(15)
        self.results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.results_container)
        
        results_main_layout.addWidget(self.scroll_area)
        
        self.apply_actions_button = QPushButton("Aplicar Acciones Seleccionadas")
        self.apply_actions_button.clicked.connect(self._confirm_and_apply_actions)
        results_main_layout.addWidget(self.apply_actions_button)
        
        main_layout.addWidget(results_widget, stretch=1)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        results_main_layout.addWidget(self.progress_bar)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(ts.t('status_ready', 'Listo.'))
        
        self.load_paths_from_cache()

    def _create_actions_and_menus(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu(ts.t('menu_file', '&Archivo'))
        settings_action = QAction(ts.t('menu_settings', '&Configuración...'), self)
        settings_action.triggered.connect(self._open_settings)
        file_menu.addAction(settings_action)
        exit_action = QAction(ts.t('menu_exit', '&Salir'), self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        view_menu = menu_bar.addMenu(ts.t('menu_view', '&Ver'))
        toggle_panel_action = QAction(ts.t('toggle_side_panel', 'Mostrar/Ocultar Panel de Rutas'), self)
        toggle_panel_action.setCheckable(True)
        toggle_panel_action.setChecked(True)
        toggle_panel_action.triggered.connect(self.toggle_side_panel)
        view_menu.addAction(toggle_panel_action)

    def toggle_side_panel(self, checked):
        self.side_panel.setVisible(checked)

    def load_paths_from_cache(self):
        self.side_panel.clear_layouts(clear_active=False, clear_history=True)
        history = self.cache.get_scanned_paths()
        for path_data in history:
            widget = PathEntryWidget(path_data['path'], is_history=True)
            widget.add_requested.connect(self.move_path_to_active)
            widget.double_clicked.connect(self.move_path_to_active)
            widget.delete_from_history_requested.connect(self._handle_delete_from_history)
            self.side_panel.history_layout.addWidget(widget)
    
    def _handle_delete_from_history(self, path: str):
        dialog = ConfirmDialog(
            parent=self,
            title="Confirmar Eliminación del Historial",
            message=f"¿Está seguro de que desea eliminar '{path}' de su historial?\n\n"
                    f"Esto borrará toda la información cacheada para esta ruta y no se podrá deshacer."
        )
        if dialog.exec():
            # 1. Eliminar de la base de datos
            self.cache.delete_scan_path(path)
            
            # 2. Refrescar la lista del historial en la UI
            self.load_paths_from_cache()
            
            self.status_bar.showMessage(f"'{path}' eliminado del historial.")

    def move_path_to_active(self, path: str):
        for i in range(self.side_panel.active_layout.count()):
            widget = self.side_panel.active_layout.itemAt(i).widget()
            if widget and widget.path == path: return
        widget = PathEntryWidget(path, is_history=False)
        widget.remove_requested.connect(self.remove_path_from_active)
        widget.double_clicked.connect(self.remove_path_from_active)
        self.side_panel.active_layout.addWidget(widget)

    def remove_path_from_active(self, path: str):
        for i in range(self.side_panel.active_layout.count()):
            widget = self.side_panel.active_layout.itemAt(i).widget()
            if widget and widget.path == path:
                widget.deleteLater()
                break
    
    def _add_new_path_to_active(self):
        directory = QFileDialog.getExistingDirectory(self, ts.t('select_folder', "Seleccionar Carpeta para Escanear"))
        if directory: self.move_path_to_active(directory)

    def _open_settings(self):
        dialog = SettingsDialog(self.config, self)
        dialog.exec()

    def _toggle_scan(self):
        if self.worker and self.worker.isRunning(): self._cancel_scan()
        else: self._start_scan()
            
    def _start_scan(self):
        paths = [self.side_panel.active_layout.itemAt(i).widget().path for i in range(self.side_panel.active_layout.count())]
        if not paths:
            QMessageBox.warning(self, ts.t('no_paths_title', 'Sin rutas'), ts.t('no_paths_body', 'Por favor, añada al menos una ruta para escanear.'))
            return
        self.scan_button.setText(ts.t('cancel_button', 'Cancelar Escaneo')); self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100); self.progress_bar.setValue(0); self._clear_results()
        scanner = DefaultScanner(); matcher = MediaNameMatcher()
        self.worker = ScanWorker(paths, scanner, matcher)
        self.worker.signals.status_update.connect(self._update_status)
        self.worker.signals.progress.connect(self.progress_bar.setValue)
        self.worker.signals.set_progress_bar_indeterminate.connect(self._set_progress_bar_indeterminate)
        self.worker.signals.finished.connect(self._scan_finished)
        self.worker.signals.results_ready.connect(self._populate_results_area)
        self.worker.signals.error.connect(self._scan_error)
        self.worker.start()

    def _set_progress_bar_indeterminate(self, is_indeterminate: bool):
        """Cambia el modo de la barra de progreso."""
        if is_indeterminate:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)

    def _cancel_scan(self):
        if self.worker: self.worker.stop()

    def _update_status(self, message):
        self.status_bar.showMessage(message)

    def _scan_finished(self):
        self.status_bar.showMessage(ts.t('status_scan_finished', 'Escaneo finalizado.'))
        self.scan_button.setText(ts.t('scan_selected_paths', 'Escanear Rutas Seleccionadas'))
        self.progress_bar.setVisible(False); self.worker = None
        self.load_paths_from_cache()

    def _scan_error(self, error_message):
        QMessageBox.critical(self, ts.t('error_title', 'Error'), error_message)

    def _clear_results(self):
        while self.results_layout.count():
            child = self.results_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        self.result_widgets.clear()

    def _populate_results_area(self, duplicate_structure: dict):
        self._clear_results()
        series_found = duplicate_structure.get("series", {}); movies_found = duplicate_structure.get("movies", [])
        
        if not series_found and not movies_found:
            no_results_label = QLabel(ts.t('no_duplicates_found', 'No se encontraron duplicados.'))
            no_results_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.results_layout.addWidget(no_results_label)
            return

        for series_title, duplicate_episodes in sorted(series_found.items()):
            series_widget = SeriesGroupWidget(series_title, duplicate_episodes)
            series_widget.ignore_series_requested.connect(self._handle_ignore_request)
            self.result_widgets[series_widget.series_id] = series_widget
            for ep_widget in series_widget.findChildren(DuplicateGroupWidget):
                ep_widget.ignore_episode_requested.connect(self._handle_ignore_request)
                self.result_widgets[ep_widget.episode_id] = ep_widget
            self.results_layout.addWidget(series_widget)
        
        if movies_found:
            movies_label = QLabel(ts.t('duplicate_movies_header', "Películas Duplicadas"))
            font = movies_label.font(); font.setPointSize(16); movies_label.setFont(font)
            movies_label.setStyleSheet("padding: 10px; background-color: #2c2c2c; margin-top: 15px;")
            self.results_layout.addWidget(movies_label)
            for movie_group in sorted(movies_found, key=lambda g: g.display_title):
                movie_id = standardize_text(movie_group.display_title)
                movie_widget = DuplicateGroupWidget(movie_group, series_id=movie_id, is_movie=True)
                movie_widget.ignore_movie_requested.connect(self._handle_ignore_request)
                self.result_widgets[movie_widget.movie_id] = movie_widget
                self.results_layout.addWidget(movie_widget)
        
        total_groups = len(movies_found) + sum(len(v) for v in series_found.values())
        self.status_bar.showMessage(f"Análisis completo. Se encontraron {total_groups} grupos de duplicados.")

    def _handle_ignore_request(self, ignore_key: str, level: str):
        dialog = ConfirmDialog(
            parent=self,
            title="Confirmar Ignorar",
            message=f"¿Desea ignorar '{ignore_key}' en futuros escaneos?\n\nEsta acción se puede revertir desde los ajustes."
        )
        if dialog.exec():
            self.cache.add_to_ignore_list(key=ignore_key, level=level)
            widget_to_remove = self.result_widgets.pop(ignore_key, None)
            if widget_to_remove:
                widget_to_remove.deleteLater()
            self.status_bar.showMessage(f"'{ignore_key}' ha sido añadido a la lista de ignorados.")
    
    def _confirm_and_apply_actions(self):
        files_to_delete = []
        for series_widget in self.results_container.findChildren(SeriesGroupWidget):
            for group_widget in series_widget.findChildren(DuplicateGroupWidget):
                for file_widget in group_widget.findChildren(FileEntryWidget):
                    if file_widget.media_file.recommendation == 'DELETE':
                        files_to_delete.append(file_widget.media_file)

        if not files_to_delete:
            QMessageBox.information(self, "Sin acciones", "No se ha marcado ningún archivo para eliminar.")
            return

        dialog = ActionConfirmDialog(files_to_delete, self)
        if dialog.exec():
            self.status_bar.showMessage("Iniciando acciones en segundo plano...")
            self.action_worker = ActionWorker(files_to_delete)
            # Conectar señales del worker de acciones en el futuro
            self.action_worker.finished.connect(self._action_worker_finished)
            self.action_worker.start()

    def _action_worker_finished(self):
        QMessageBox.information(self, "Acciones Completadas", "Los archivos seleccionados han sido enviados a la papelera.")
        self.status_bar.showMessage("Acciones completadas. Refrescando...")
        self._start_scan() # Refrescar la vista