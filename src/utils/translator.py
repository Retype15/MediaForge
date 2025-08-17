import json
import os
import sys

class Translator:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Translator, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.translations = {}
            self.language = "es_ES"
            self.initialized = True
    
    def get_base_path(self):
        # Obtiene la ruta base, funciona tanto en desarrollo como en un ejecutable de PyInstaller
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(os.path.abspath(__file__))

    def load_language(self, lang_code="es_ES"):
        self.language = lang_code
        # Navegar desde 'src/utils' hasta 'assets/translations'
        base_path = self.get_base_path()
        translations_dir = os.path.join(base_path, '..', '..', 'assets', 'translations')
        file_path = os.path.normpath(os.path.join(translations_dir, f"{lang_code}.json"))
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.translations = json.load(f)
        except FileNotFoundError:
            print(f"Warning: Translation file not found: {file_path}")
            self.translations = {}

    def t(self, key, default_text=""):
        return self.translations.get(key, default_text)

ts = Translator()