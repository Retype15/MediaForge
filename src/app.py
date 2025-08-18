import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt

from src.core.config_manager import ConfigManager
from src.utils.translator import ts
from src.utils.metadata_extractor import MetadataExtractor
from src.core.cache_manager import CacheManager
from src.ui.hub_window import HubWindow
from src.ui.duplicate_finder_window import DuplicateFinderWindow

class App:
    def __init__(self):
        self.qt_app = QApplication(sys.argv)
        self.config_manager = ConfigManager()
        self.cache_manager = CacheManager()
        self.current_tool_window = None

        # --- Definición de las herramientas disponibles ---
        self.TOOLS_CONFIG = [
            {
                'id': 'duplicate_finder',
                'name': ts.t('tool_duplicate_finder_name', 'Buscador de Duplicados'),
                'icon': 'assets/images/duplicate_icon.png', # Necesitarás este icono
                'class': DuplicateFinderWindow
            },
            # ... Aquí añadirías futuras herramientas ...
            # {
            #     'id': 'media_organizer',
            #     'name': ts.t('tool_media_organizer_name', 'Organizador de Medios'),
            #     'icon': 'assets/images/organizer_icon.png',
            #     'class': MediaOrganizerWindow # Una futura clase
            # },
        ]
        
        self._setup_style()
        self._setup_translator()
        self._setup_ffmpeg_path()
        
        # --- Lógica de arranque modificada ---
        self.hub_window = HubWindow(self.TOOLS_CONFIG, self.config_manager)
        self.hub_window.tool_launched.connect(self.launch_tool)

    def launch_tool(self, tool_id: str):
        tool_data = next((tool for tool in self.TOOLS_CONFIG if tool['id'] == tool_id), None)
        if not tool_data:
            print(f"Error: No se encontró la herramienta con ID '{tool_id}'")
            return

        # Ocultar el hub antes de mostrar la herramienta para evitar parpadeos
        self.hub_window.hide()

        ToolWindowClass = tool_data['class']
        self.current_tool_window = ToolWindowClass(self.config_manager, self.cache_manager)
        
        # Conectar la señal de cierre para volver a mostrar el hub
        self.current_tool_window.closing.connect(self.show_hub)
        
        self.current_tool_window.show()

    def show_hub(self):
        self.current_tool_window = None # Liberar la referencia
        self.hub_window.show()
        # Aquí podrías refrescar la lista de "recientes" si la implementas

    def _setup_style(self):
        self.qt_app.setStyle("Fusion")
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        self.qt_app.setPalette(dark_palette)
        
    def _setup_translator(self):
        language = self.config_manager.get("general/language", "es_ES")
        ts.load_language(language)

    def _setup_ffmpeg_path(self): # <-- NUEVA FUNCIÓN
        ffmpeg_path = self.config_manager.get("general/ffmpeg_path", "")
        MetadataExtractor.set_ffmpeg_path(ffmpeg_path)

    def run(self):
        self.hub_window.show()
        sys.exit(self.qt_app.exec())