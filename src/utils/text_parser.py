from typing import Optional, Tuple
import re

RE_EPISODE_PATTERNS = [
    (re.compile(r'[._\s-][Ss]([0-9]{1,2})[._\s-]?[Ee]([0-9]{1,3}(?:\.5)?)[._\s-]?'), 'SE'),
    (re.compile(r'[._\s-]([0-9]{1,2})[xX]([0-9]{1,3}(?:\.5)?)[._\s-]?'), 'SE'),
    (re.compile(r'[._\s-][Ss]([0-9]{1,2})(?:[._\s-]?[EeSs][0-9]{1,2})*[._\s-]?[Ee]([0-9]{1,3}(?:\.5)?)'), 'MULTI_SE'),
    (re.compile(r'(?:^|[\s_.-])([0-9]{1,3}(?:\.5)?)(?:\.\w+$|[\s_.-])'), 'E_ONLY_ISOLATED'),
]
RE_SEASON_ONLY = re.compile(r'[._\s-][Ss](eason)?[._\s-]?([0-9]{1,2})[._\s-]?')

def robust_parse_episode(filename: str) -> Optional[Tuple[int, float]]:
    for pattern, p_type in RE_EPISODE_PATTERNS:
        match = pattern.search(filename)
        if match:
            try:
                if p_type == 'SE':
                    return int(match.group(1)), float(match.group(2).replace(',', '.'))
                if p_type == 'MULTI_SE':
                    return int(match.group(1)), float(match.group(2).replace(',', '.'))
                if p_type == 'E_ONLY_ISOLATED':
                    season_match = RE_SEASON_ONLY.search(filename)
                    season = int(season_match.group(2)) if season_match else 1
                    return season, float(match.group(1).replace(',', '.'))
            except (ValueError, IndexError):
                continue
    return None

def standardize_text(text: str) -> str:
    clean = text.lower()
    clean = re.sub(r'[\(\[].*?[\)\]]', '', clean)
    clean = re.sub(r'season|temporada', 's', clean)
    clean = re.sub(r'episode|episodio', 'e', clean)
    clean = re.sub(r'[\._\-]', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean