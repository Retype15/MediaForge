from PyQt6.QtCore import QThread, pyqtSignal
from typing import List
from src.core.models import MediaFile
# pip install send2trash
import send2trash

class ActionWorker(QThread):
    def __init__(self, files_to_delete: List[MediaFile]):
        super().__init__()
        self.files_to_delete = files_to_delete

    def run(self):
        for file in self.files_to_delete:
            try:
                send2trash.send2trash(str(file.path))
            except Exception as e:
                print(f"No se pudo eliminar {file.path}: {e}")
        # Aquí se podrían emitir señales de progreso y finalización