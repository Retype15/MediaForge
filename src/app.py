import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt

from src.core.config_manager import ConfigManager
from src.utils.translator import ts
from src.ui.main_window import MainWindow
from src.utils.metadata_extractor import MetadataExtractor
from src.core.cache_manager import CacheManager

class App:
    def __init__(self):
        self.qt_app = QApplication(sys.argv)
        self.config_manager = ConfigManager()
        self.cache_manager = CacheManager()
        
        self._setup_style()
        self._setup_translator()
        self._setup_ffmpeg_path() # <-- NUEVA LLAMADA
        
        self.main_window = MainWindow(self.config_manager, self.cache_manager)

    def _setup_style(self):
        # ... (sin cambios) ...
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
        self.main_window.show()
        sys.exit(self.qt_app.exec())