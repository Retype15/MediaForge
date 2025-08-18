# --- START OF FILE src/ui/hub_window.py ---

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QScrollArea, 
                             QGridLayout, QLabel)
from PyQt6.QtCore import pyqtSignal, Qt
from src.ui.widgets.tool_widgets import ToolButtonWidget
from src.utils.translator import ts

class HubWindow(QMainWindow):
    tool_launched = pyqtSignal(str)

    def __init__(self, tools_config, config_manager):
        super().__init__()
        self.tools = tools_config
        self.config = config_manager

        self.setWindowTitle(ts.t('app_title', 'MediaForge'))
        self.setGeometry(200, 200, 800, 600)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QVBoxLayout(self.central_widget)

        # Título principal
        title_label = QLabel(ts.t('hub_title', "Panel de Herramientas"))
        font = title_label.font()
        font.setPointSize(24)
        title_label.setFont(font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        # Área de herramientas con scroll
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.tools_container = QWidget()
        self.tools_layout = QGridLayout(self.tools_container)
        self.tools_layout.setSpacing(20)
        self.tools_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.scroll_area.setWidget(self.tools_container)

        main_layout.addWidget(self.scroll_area)
        
        self._populate_tools()

        self.load_settings()

    def _populate_tools(self):
        col_count = self._calculate_columns()
        for i, tool in enumerate(self.tools):
            row, col = divmod(i, col_count)
            tool_button = ToolButtonWidget(tool['id'], tool['name'], tool['icon'])
            tool_button.clicked.connect(self.tool_launched.emit)
            self.tools_layout.addWidget(tool_button, row, col)

    def _calculate_columns(self):
        # Simple cálculo para responsividad
        width = self.width()
        return max(1, (width - 50) // (150 + 20)) # 150 = ancho widget, 20 = spacing

    def resizeEvent(self, event):
        # Reorganizar la cuadrícula al cambiar el tamaño de la ventana
        self._reorganize_grid()
        super().resizeEvent(event)

    def _reorganize_grid(self):
        col_count = self._calculate_columns()
        items = []
        while self.tools_layout.count():
            items.append(self.tools_layout.takeAt(0))
        
        for i, item in enumerate(items):
            row, col = divmod(i, col_count)
            self.tools_layout.addWidget(item.widget(), row, col)
    
    def load_settings(self):
        geometry = self.config.get("hub_window/geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def closeEvent(self, event):
        self.config.set("hub_window/geometry", self.saveGeometry())
        super().closeEvent(event)