from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QListWidget, QDialogButtonBox
from typing import List
from src.core.models import MediaFile

class ConfirmDialog(QDialog):
    """Un diálogo de confirmación genérico."""
    def __init__(self, parent=None, title="Confirmar", message="¿Está seguro?"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(350)
        
        layout = QVBoxLayout(self)
        label = QLabel(message)
        label.setWordWrap(True)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        layout.addWidget(label)
        layout.addWidget(buttons)

class ActionConfirmDialog(QDialog):
    def __init__(self, files_to_delete: List[MediaFile], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirmar Eliminación")
        self.setMinimumSize(500, 300)
        
        layout = QVBoxLayout(self)
        label = QLabel(f"¿Está seguro de que desea enviar los siguientes {len(files_to_delete)} archivos a la papelera?")
        label.setWordWrap(True)
        self.file_list = QListWidget()
        for file in files_to_delete:
            self.file_list.addItem(str(file.path))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(label)
        layout.addWidget(self.file_list)
        layout.addWidget(buttons)