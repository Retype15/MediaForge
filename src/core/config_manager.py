from PyQt6.QtCore import QSettings

ORGANIZATION_NAME = "MediaForgeProject"
APPLICATION_NAME = "MediaForge"

class ConfigManager:
    def __init__(self):
        self.settings = QSettings(ORGANIZATION_NAME, APPLICATION_NAME)

    def get(self, key, default=None):
        return self.settings.value(key, default)

    def set(self, key, value):
        self.settings.setValue(key, value)