from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional

@dataclass
class MediaFile:
    path: Path
    size: int
    mtime: float
    parsed_info: Dict = field(default_factory=dict)
    metadata_info: Optional[Dict] = None
    
    # Valores: 'REVIEW', 'SUGGESTED', 'KEEP', 'DELETE'
    recommendation: str = 'REVIEW'
    reason: str = ""

    # ... (propiedades sin cambios)
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
        ep = self.parsed_info.get('episode')
        return float(ep) if ep is not None else None
    @property
    def is_series_episode(self) -> bool:
        return 'season' in self.parsed_info and 'episode' in self.parsed_info

@dataclass
class DuplicateGroup:
    group_id: str
    files: List[MediaFile]
    display_title: str