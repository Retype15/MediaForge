import re
from typing import List, Dict, Optional
import PTN
from collections import defaultdict
from src.modules.base import MatcherBase
from src.core.models import MediaFile, DuplicateGroup

# Expresiones regulares precompiladas para eficiencia
# Elimina info de calidad, fuente, grupo, etc.
RE_CLEAN_BRACKETS = re.compile(r'[\(\[].*?[\)\]]')
# Elimina extensiones de archivo
RE_CLEAN_EXTENSION = re.compile(r'\.\w+$')
# Patrones de episodio, del más específico al más general.
# El orden es CRÍTICO.
RE_EPISODE_PATTERNS = [
    # Formatos como S01E01, 1x01, T1E1
    re.compile(r'[._\s-][Ss]([0-9]{1,2})[._\s-]?[Ee]([0-9]{1,4})[._\s-]?'),
    re.compile(r'[._\s-]([0-9]{1,2})[xX]([0-9]{1,4})[._\s-]?'),
    re.compile(r'[._\s-][Tt]([0-9]{1,2})[._\s-]?[Ee]([0-9]{1,4})[._\s-]?'),
    # Formato de 3 o 4 dígitos (101 = S01E01) excluyendo años comunes o 1080/720
    re.compile(r'[._\s-](?<![12]\d{3}\s)(?<!1080)(?<!720)([1-9])([0-9]{2,3})[._\s-]?'),
    # Número de episodio simple, a menudo al final.
    re.compile(r'[._\s-](?:EP|ep|Ep|e|E)?([0-9]{1,4})[._\s-]?'),
]

def extract_clean_title(filename: str) -> str:
    """Crea una 'huella digital' del título eliminando todo lo que no sea el nombre."""
    # Hacemos una copia para no modificar el original
    clean_name = filename
    
    # Eliminar contenido entre corchetes y paréntesis
    clean_name = RE_CLEAN_BRACKETS.sub('', clean_name)
    
    # Eliminar extensión de archivo
    clean_name = RE_CLEAN_EXTENSION.sub('', clean_name)
    
    # Eliminar información de episodio usando los mismos patrones
    for pattern in RE_EPISODE_PATTERNS:
        clean_name = pattern.sub('', clean_name)
    
    # Normalizar reemplazando separadores por espacios
    clean_name = re.sub(r'[\._\-]', ' ', clean_name)
    # Eliminar espacios extra y dejarlo en minúsculas
    clean_name = re.sub(r'\s+', ' ', clean_name).strip().lower()
    
    return clean_name

def robust_parse_episode(filename: str) -> Optional[Dict]:
    """Parsea temporada y episodio con una lógica mucho más estricta."""
    for i, pattern in enumerate(RE_EPISODE_PATTERNS):
        # Buscamos de derecha a izquierda, ya que la info de episodio suele estar al final
        match = None
        for m in pattern.finditer(filename):
            match = m
        
        if match:
            if i < 3: # S01E01, 1x01, T1E1
                return {'season': int(match.group(1)), 'episode': int(match.group(2))}
            if i == 3: # 101 -> S01E01
                return {'season': int(match.group(1)), 'episode': int(match.group(2))}
            if i == 4: # - 01
                # Evitar coincidencias con años o resoluciones
                ep_num = int(match.group(1))
                if 1900 < ep_num < 2100 or ep_num in [480, 720, 1080, 2160]:
                    continue
                return {'season': 1, 'episode': ep_num}
    return None

class MediaNameMatcher(MatcherBase):
    """
    Agrupa archivos usando una estrategia de "Clustering por Huella Digital del Título":
    1. Para cada archivo, extrae un "título limpio" (huella digital).
    2. Agrupa todos los archivos con la misma huella.
    3. Dentro de cada grupo, identifica duplicados por número de episodio.
    """
    def get_name(self) -> str:
        return "Matcher por Huella de Título (Recomendado)"

    def get_id(self) -> str:
        return "title_fingerprint_matcher"

    def find_duplicates(self, files: List[MediaFile]) -> Dict[str, List[DuplicateGroup]]:
        clusters = defaultdict(list)
        
        # Paso 1: Parsear cada archivo y asignarlo a un clúster
        for file in files:
            clean_title = extract_clean_title(file.path.name)
            ep_info = robust_parse_episode(file.path.name)
            
            # Usamos PTN solo para info secundaria (calidad, etc.)
            ptn_info = PTN.parse(file.path.name)
            file.parsed_info = ptn_info
            
            if ep_info:
                file.parsed_info.update(ep_info) # Nuestra info de episodio es más fiable
            
            clusters[clean_title].append(file)

        # Paso 2: Procesar cada clúster para encontrar duplicados internos
        results = {"movies": [], "series": {}}
        for title_fingerprint, media_files in clusters.items():
            if not media_files: continue

            # Determinar si el clúster es una serie o un conjunto de películas
            episode_files = [f for f in media_files if f.is_series_episode]
            movie_files = [f for f in media_files if not f.is_series_episode]
            
            is_likely_series = len(episode_files) > len(media_files) / 2

            if is_likely_series:
                # El título canónico será el de la carpeta más común o el nombre más largo
                canonical_title = max(set(f.path.parent.name for f in media_files), key=len)
                
                episodes_in_cluster = defaultdict(list)
                for file in episode_files:
                    episode_key = f"s{file.season:02d}e{file.episode:02d}"
                    episodes_in_cluster[episode_key].append(file)
                
                duplicate_episodes = []
                for episode_key, file_list in episodes_in_cluster.items():
                    if len(file_list) > 1:
                        first_file = file_list[0]
                        display_title = f"S{first_file.season:02d}E{first_file.episode:02d}"
                        group = DuplicateGroup(group_id=episode_key, files=file_list, display_title=display_title)
                        duplicate_episodes.append(group)
                
                if duplicate_episodes:
                    results["series"][canonical_title] = duplicate_episodes
            else: # Tratar como películas
                # Si todos los archivos del clúster tienen el mismo nombre limpio, son duplicados de la misma película
                if len(media_files) > 1:
                    first_file = media_files[0]
                    display_title = first_file.title
                    if first_file.year:
                        display_title += f" ({first_file.year})"
                    group = DuplicateGroup(group_id=title_fingerprint, files=media_files, display_title=display_title)
                    results["movies"].append(group)
                    
        return results