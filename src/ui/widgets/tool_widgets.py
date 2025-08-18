# --- START OF FILE src/ui/widgets/tool_widgets.py ---

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QSizePolicy
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, pyqtSignal

class ToolButtonWidget(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, tool_id: str, name: str, icon_path: str, parent=None):
        super().__init__(parent)
        self.tool_id = tool_id
        self.setFixedSize(150, 150)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("ToolButtonWidget")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.icon_label = QLabel()
        self.icon_label.setScaledContents(True)
        self.icon_label.setFixedSize(80, 80)
        self.icon_label.setPixmap(QPixmap(icon_path))
        self.icon_label.setObjectName("IconLabel")
        
        self.name_label = QLabel(name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(True)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.name_label)

        # Estilo para hacer el icono circular
        self.setStyleSheet("""
            #ToolButtonWidget {
                background-color: #3a3a3a;
                border-radius: 10px;
            }
            #ToolButtonWidget:hover {
                background-color: #4a4a4a;
                border: 1px solid #5c5c5c;
            }
            #IconLabel {
                border: 2px solid #555;
                border-radius: 40px; /* La mitad del tamaño (80px) */
                padding: 5px;
            }
        """)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.tool_id)
        super().mouseReleaseEvent(event)