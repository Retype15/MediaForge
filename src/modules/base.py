from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Generator
from src.core.models import MediaFile, DuplicateGroup

class ScannerBase(ABC):
    """Interfaz para todos los módulos de escaneo."""
    @abstractmethod
    def scan(self, path: Path) -> Generator[Path, None, None]:
        """Escanea una ruta y devuelve un generador de archivos multimedia."""
        pass

class MatcherBase(ABC):
    """Interfaz para todos los módulos de identificación (matching)."""
    @abstractmethod
    def get_name(self) -> str:
        """Devuelve el nombre del módulo para mostrar en la UI."""
        pass

    @abstractmethod
    def get_id(self) -> str:
        """Devuelve un identificador único para la configuración."""
        pass
    
    @abstractmethod
    def find_duplicates(self, files: List[MediaFile]) -> List[DuplicateGroup]:
        """Procesa la lista de archivos y devuelve los grupos de duplicados."""
        pass