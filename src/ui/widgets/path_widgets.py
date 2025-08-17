from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QScrollArea, QFrame, QSizePolicy, QMenu)
from PyQt6.QtGui import QFont, QAction, QDesktopServices
from PyQt6.QtCore import Qt, QUrl, pyqtSignal # <-- pyqtSignal
import os

# ... (función get_volume_name sin cambios) ...
def get_volume_name(path_str: str) -> str:
    try:
        drive_letter = os.path.splitdrive(path_str)[0]
        if os.name == 'nt':
            vol_output = os.popen(f"vol {drive_letter}").read()
            lines = vol_output.splitlines()
            for line in lines:
                if "volumen en la unidad" in line or "Volume in drive" in line:
                    volume_label = line.split(" es " if " es " in line else " is ")[-1].strip()
                    if volume_label:
                        return f"{volume_label} ({drive_letter})"
        return f"Disco ({drive_letter})"
    except Exception:
        return os.path.splitdrive(path_str)[0] or "Ubicación"

# ... (función compact_path sin cambios) ...
def compact_path(path_str: str, max_len: int = 40) -> str:
    if len(path_str) <= max_len: return path_str
    parts = path_str.split(os.path.sep)
    if len(parts) <= 3: return path_str
    return f"{parts[0]}{os.path.sep}...{os.path.sep}{os.path.sep.join(parts[-2:])}"

class PathEntryWidget(QFrame):
    add_requested = pyqtSignal(str)
    remove_requested = pyqtSignal(str)
    delete_from_history_requested = pyqtSignal(str)
    # --- INICIO DE CORRECCIÓN: NUEVA SEÑAL ---
    double_clicked = pyqtSignal(str)
    # --- FIN DE CORRECCIÓN ---

    def __init__(self, path: str, is_history: bool = True, parent=None):
        # ... (el __init__ se mantiene igual hasta el final) ...
        super().__init__(parent)
        self.path = path
        self.is_history = is_history
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setObjectName("PathEntryWidget")
        self.setStyleSheet("""
            #PathEntryWidget { background-color: transparent; border: 1px solid #2c2c2c; border-radius: 3px; margin: 2px 0; }
            #PathEntryWidget:hover { background-color: #4a4a4a; }
        """)
        main_layout = QHBoxLayout(self)
        text_layout = QVBoxLayout(); text_layout.setSpacing(0)
        volume_label = QLabel(get_volume_name(path))
        font = volume_label.font(); font.setBold(True); volume_label.setFont(font)
        path_label = QLabel(compact_path(path)); path_label.setStyleSheet("color: #aaa;")
        text_layout.addWidget(volume_label); text_layout.addWidget(path_label)
        main_layout.addLayout(text_layout, stretch=1)
        self.setToolTip(path)
        open_button = QPushButton("📂"); open_button.setFixedSize(30, 30); open_button.setToolTip("Abrir ubicación en el explorador")
        open_button.clicked.connect(self._open_path)
        main_layout.addWidget(open_button)
        if self.is_history:
            action_button = QPushButton("+"); action_button.setFixedSize(30, 30); action_button.setToolTip("Añadir a la cola de escaneo")
            action_button.clicked.connect(lambda: self.add_requested.emit(self.path))
        else:
            action_button = QPushButton("-"); action_button.setFixedSize(30, 30); action_button.setToolTip("Quitar de la cola de escaneo")
            action_button.clicked.connect(lambda: self.remove_requested.emit(self.path))
        main_layout.addWidget(action_button)
    
    # --- INICIO DE CORRECCIÓN: EVENTO DOBLE CLIC ---
    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit(self.path)
        event.accept()
    # --- FIN DE CORRECCIÓN ---

    # ... (el resto de la clase se mantiene sin cambios) ...
    def _open_path(self):
        try:
            os.startfile(self.path)
        except AttributeError: QDesktopServices.openUrl(QUrl.fromLocalFile(self.path))
        except FileNotFoundError: print(f"Path not found: {self.path}")
    def contextMenuEvent(self, event):
        context_menu = QMenu(self)
        open_action = QAction("Abrir Ruta", self)
        open_action.triggered.connect(self._open_path)
        context_menu.addAction(open_action)
        if self.is_history:
            context_menu.addSeparator()
            delete_action = QAction("Eliminar del Historial", self)
            delete_action.triggered.connect(lambda: self.delete_from_history_requested.emit(self.path))
            context_menu.addAction(delete_action)
        context_menu.exec(event.globalPos())

# ... (la clase SidePanel se mantiene sin cambios) ...
class SidePanel(QWidget):
    add_path_requested = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(350); self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        active_label = QLabel("Rutas para Escanear")
        font = active_label.font(); font.setBold(True); active_label.setFont(font)
        add_new_path_button = QPushButton("Añadir Nueva Ruta...")
        add_new_path_button.clicked.connect(lambda: self.add_path_requested.emit())
        self.active_scroll = QScrollArea(); self.active_widget = QWidget()
        self.active_layout = QVBoxLayout(self.active_widget); self.active_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.active_scroll.setWidgetResizable(True); self.active_scroll.setWidget(self.active_widget)
        self.main_layout.addWidget(active_label); self.main_layout.addWidget(add_new_path_button)
        self.main_layout.addWidget(self.active_scroll, stretch=1)
        history_label = QLabel("Historial de Escaneo")
        history_label.setFont(font)
        self.history_scroll = QScrollArea(); self.history_widget = QWidget()
        self.history_layout = QVBoxLayout(self.history_widget); self.history_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.history_scroll.setWidgetResizable(True); self.history_scroll.setWidget(self.history_widget)
        self.main_layout.addWidget(history_label); self.main_layout.addWidget(self.history_scroll, stretch=2)
    
    def clear_layouts(self, clear_active=True, clear_history=True):
        if clear_active:
            while self.active_layout.count():
                child = self.active_layout.takeAt(0)
                if child.widget(): child.widget().deleteLater()
        
        if clear_history:
            while self.history_layout.count():
                child = self.history_layout.takeAt(0)
                if child.widget(): child.widget().deleteLater()