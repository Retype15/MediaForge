from typing import List
from src.core.models import MediaFile, DuplicateGroup

def get_quality_score(media_file: MediaFile) -> int:
    """Asigna una puntuación numérica a la calidad del video."""
    if media_file.metadata_info and media_file.metadata_info.get('height', 0) > 0:
        height = media_file.metadata_info['height']
        if height >= 2160: return 5 # 4K
        if height >= 1080: return 4 # 1080p
        if height >= 720: return 3 # 720p
        if height >= 480: return 2 # 480p
        return 1 # SD
    
    # Fallback a la info parseada del nombre
    resolution = media_file.parsed_info.get('resolution', '').lower()
    if '4k' in resolution or '2160p' in resolution: return 5
    if '1080p' in resolution: return 4
    if '720p' in resolution: return 3
    if '480p' in resolution: return 2
    return 0 # Desconocido

class Recommender:
    def __init__(self, priority_order: List[str]):
        self.priority_order = priority_order

    def apply_recommendations(self, group: DuplicateGroup):
        """
        Aplica las reglas de recomendación a un grupo de archivos duplicados.
        Modifica los objetos MediaFile dentro del grupo.
        """
        if not group.files or len(group.files) < 2:
            return

        candidates = list(group.files)
        
        for rule_key in self.priority_order:
            if len(candidates) == 1:
                break # Ya hemos encontrado un ganador

            best_of_rule = []
            
            if rule_key == "quality_desc":
                max_quality = max(get_quality_score(f) for f in candidates)
                best_of_rule = [f for f in candidates if get_quality_score(f) == max_quality]
            
            elif rule_key == "size_desc":
                max_size = max(f.size for f in candidates)
                best_of_rule = [f for f in candidates if f.size == max_size]

            elif rule_key == "size_asc":
                min_size = min(f.size for f in candidates)
                best_of_rule = [f for f in candidates if f.size == min_size]

            elif rule_key == "mtime_desc":
                max_mtime = max(f.mtime for f in candidates)
                best_of_rule = [f for f in candidates if f.mtime == max_mtime]

            elif rule_key == "mtime_asc":
                min_mtime = min(f.mtime for f in candidates)
                best_of_rule = [f for f in candidates if f.mtime == min_mtime]
            
            # Si la regla produjo un resultado (y no un empate idéntico), actualizamos los candidatos
            if best_of_rule and len(best_of_rule) < len(candidates):
                candidates = best_of_rule

        # Al final, el primer candidato de la lista es el ganador
        winner = candidates[0]
        
        # Marcamos las recomendaciones
        for file in group.files:
            if file is winner:
                file.recommendation = 'KEEP'
                file.reason = "Seleccionado como la mejor versión según tus prioridades."
            else:
                file.recommendation = 'DELETE'
                file.reason = "Hay una versión mejor disponible."