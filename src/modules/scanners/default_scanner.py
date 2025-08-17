from pathlib import Path
from typing import Generator
from src.modules.base import ScannerBase

class DefaultScanner(ScannerBase):
    """Un escáner simple que busca archivos de video comunes."""
    
    VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm'}

    def scan(self, path: Path) -> Generator[Path, None, None]:
        if not path.is_dir():
            return
        
        for file_path in path.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in self.VIDEO_EXTENSIONS:
                yield file_path