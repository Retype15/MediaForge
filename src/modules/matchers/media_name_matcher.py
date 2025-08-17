import re
from typing import List, Dict, Optional, Set, Tuple
from collections import defaultdict
from thefuzz import fuzz # type: ignore
from pathlib import Path
from src.modules.base import MatcherBase
from src.core.models import MediaFile, DuplicateGroup

# --- Parseo de Episodios (la versión más robusta hasta ahora) ---
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
    # Estandarización más agresiva
    clean = text.lower()
    clean = re.sub(r'[\(\[].*?[\)\]]', '', clean) # Eliminar corchetes/paréntesis
    clean = re.sub(r'season|temporada', 's', clean) # Estandarizar temporada
    clean = re.sub(r'episode|episodio', 'e', clean) # Estandarizar episodio
    clean = re.sub(r'[\._\-]', ' ', clean) # Reemplazar separadores
    clean = re.sub(r'\s+', ' ', clean).strip() # Eliminar espacios extra
    return clean

# --- Lógica de la Entidad Canónica (una por carpeta) ---
class MediaEntity:
    def __init__(self, folder_path: Path, files: List[MediaFile]):
        self.folder_path = folder_path
        self.files = files
        self.standardized_folder_name = standardize_text(folder_path.name)
        self.standardized_titles = {standardize_text(f.path.name) for f in files}
        self.episodes: Dict[Tuple[int, float], List[MediaFile]] = defaultdict(list)
        for f in files:
            if f.is_series_episode:
                self.episodes[(f.season, f.episode)].append(f)
    
    def merge(self, other_entity):
        self.files.extend(other_entity.files)
        # Al fusionar, el nombre canónico se convierte en el más largo/descriptivo
        if len(other_entity.standardized_folder_name) > len(self.standardized_folder_name):
            self.standardized_folder_name = other_entity.standardized_folder_name
        self.standardized_titles.update(other_entity.standardized_titles)
        for key, files in other_entity.episodes.items():
            self.episodes[key].extend(files)

    @property
    def canonical_title(self) -> str:
        # Intenta usar el nombre de la carpeta original como título
        return self.folder_path.name

def get_similarity_score(entity_a: MediaEntity, entity_b: MediaEntity) -> float:
    if bool(entity_a.episodes) != bool(entity_b.episodes): return 0.0

    # 1. CONTEXTO (CARPETA) - Peso: 0.45
    folder_score = fuzz.partial_ratio(entity_a.standardized_folder_name, entity_b.standardized_folder_name) / 100.0

    # 2. CONTENIDO (NOMBRES DE ARCHIVO) - Peso: 0.25
    title_score = fuzz.token_set_ratio(" ".join(entity_a.standardized_titles), " ".join(entity_b.standardized_titles)) / 100.0

    # 3. ESTRUCTURA (EPISODIOS) - Peso: 0.15
    eps_a, eps_b = set(entity_a.episodes.keys()), set(entity_b.episodes.keys())
    if not eps_a and not eps_b: # Películas
        structure_score = 0.5 # Neutral
    elif not eps_a.intersection(eps_b): # Series sin episodios en común
        return 0.0
    else:
        intersection = len(eps_a.intersection(eps_b))
        union = len(eps_a.union(eps_b))
        structure_score = intersection / union

    # 4. FÍSICA (DURACIÓN) - Peso: 0.15
    metadata_scores = []
    for ep_key in eps_a.intersection(eps_b):
        # ... (lógica interna de comparación de duración se mantiene)
        files_a, files_b = entity_a.episodes[ep_key], entity_b.episodes[ep_key]
        for fa in files_a:
            for fb in files_b:
                if fa.metadata_info and fb.metadata_info:
                    dur_a, dur_b = fa.metadata_info.get('duration', 0), fb.metadata_info.get('duration', 0)
                    if dur_a > 1 and dur_b > 1:
                        diff = abs(dur_a - dur_b) / max(dur_a, dur_b)
                        if diff > 0.10: return 0.0 # Veto suave si la duración es muy diferente
                        score = max(0, 1 - (diff / 0.05))
                        metadata_scores.append(score)
    avg_duration_score = sum(metadata_scores) / len(metadata_scores) if metadata_scores else 0.5
    
    # PUNTUACIÓN FINAL PONDERADA (de 0 a 100)
    final_score = (
        (folder_score * 0.45) +
        (title_score * 0.25) +
        (structure_score * 0.15) +
        (avg_duration_score * 0.15)
    ) * 100

    return final_score

# --- El Matcher Principal (v6) ---
class MediaNameMatcher(MatcherBase):
    SIMILARITY_THRESHOLD = 65.0

    def get_name(self) -> str:
        return "Matcher por Entidades Canónicas (v6)"

    def get_id(self) -> str:
        return "canonical_entity_matcher_v6"

    def find_duplicates(self, files: List[MediaFile]) -> Dict[str, List[DuplicateGroup]]:
        # 1. Parsear todos los archivos
        for file in files:
            file.parsed_info = {}
            ep_info = robust_parse_episode(file.path.name)
            if ep_info:
                file.parsed_info['season'], file.parsed_info['episode'] = ep_info

        # 2. Crear Entidades Canónicas por carpeta
        files_by_folder = defaultdict(list)
        for file in files:
            files_by_folder[file.path.parent].append(file)
        
        entities = [MediaEntity(path, folder_files) for path, folder_files in files_by_folder.items()]
        
        # 3. Fusión iterativa de entidades
        merged_in_pass = True
        while merged_in_pass:
            merged_in_pass = False
            i = 0
            while i < len(entities):
                j = i + 1
                while j < len(entities):
                    score = get_similarity_score(entities[i], entities[j])
                    if score >= self.SIMILARITY_THRESHOLD:
                        entities[i].merge(entities.pop(j))
                        merged_in_pass = True
                    else:
                        j += 1
                i += 1
        
        # 4. Generar resultados finales
        results = {"movies": [], "series": {}}
        for entity in entities:
            # ... (la lógica de generación de resultados se mantiene igual que la v5)
            has_duplicates = False
            if not entity.episodes and len(entity.files) > 1: has_duplicates = True
            else:
                for file_list in entity.episodes.values():
                    if len(file_list) > 1:
                        has_duplicates = True
                        break
            if not has_duplicates: continue

            if entity.episodes:
                duplicate_episodes = []
                sorted_episodes = sorted(entity.episodes.items(), key=lambda item: item[0])
                for ep_key, file_list in sorted_episodes:
                    if len(file_list) > 1:
                        season, episode_num = ep_key
                        episode_str = f"{episode_num:.1f}".replace('.0', '') if episode_num % 1 else f"{int(episode_num):02d}"
                        display_title = f"S{season:02d}E{episode_str}"
                        group = DuplicateGroup(group_id=f"{season}-{episode_num}", files=file_list, display_title=display_title)
                        duplicate_episodes.append(group)
                if duplicate_episodes:
                    results["series"][entity.canonical_title] = duplicate_episodes
            elif len(entity.files) > 1:
                group = DuplicateGroup(group_id=entity.canonical_title, files=entity.files, display_title=entity.canonical_title)
                results["movies"].append(group)
        
        return results