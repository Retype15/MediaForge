from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional

@dataclass
class MediaFile:
    """Representa un único archivo multimedia y su información relevante."""
    path: Path
    size: int
    mtime: float
    parsed_info: Dict = field(default_factory=dict)
    metadata_info: Optional[Dict] = None

    recommendation: str = 'REVIEW'  # Valores: 'KEEP', 'DELETE', 'REVIEW'
    reason: str = "" # Por qué se hizo esta recomendación

    @property
    def title(self) -> str:
        return self.parsed_info.get('series', self.parsed_info.get('title', 'Unknown'))

    @property
    def year(self) -> Optional[int]:
        return self.parsed_info.get('year')

    @property
    def season(self) -> Optional[int]:
        return self.parsed_info.get('season')

    @property
    def episode(self) -> Optional[float]:
        return self.parsed_info.get('episode')
    
    @property
    def is_series_episode(self) -> bool:
        return 'season' in self.parsed_info and 'episode' in self.parsed_info

@dataclass
class DuplicateGroup:
    """Representa un grupo de archivos que son considerados duplicados."""
    group_id: str
    files: List[MediaFile]
    display_title: str