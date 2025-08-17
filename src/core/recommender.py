from typing import List
from src.core.models import MediaFile, DuplicateGroup

def get_quality_score(media_file: MediaFile) -> int:
    if media_file.metadata_info and media_file.metadata_info.get('height', 0) > 0:
        height = media_file.metadata_info['height']
        if height >= 2160: return 5
        if height >= 1080: return 4
        if height >= 720: return 3
        if height >= 480: return 2
        return 1
    resolution = media_file.parsed_info.get('resolution', '').lower()
    if '4k' in resolution or '2160p' in resolution: return 5
    if '1080p' in resolution: return 4
    if '720p' in resolution: return 3
    if '480p' in resolution: return 2
    return 0

class Recommender:
    def __init__(self, priority_order: List[str]):
        self.priority_order = priority_order

    def apply_recommendations(self, group: DuplicateGroup):
        if not group.files or len(group.files) < 2:
            for file in group.files:
                file.recommendation = 'REVIEW'
            return

        candidates = list(group.files)
        
        for rule_key in self.priority_order:
            if len(candidates) == 1: break
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
            
            if best_of_rule and len(best_of_rule) < len(candidates):
                candidates = best_of_rule

        winner = candidates[0]
        
        for file in group.files:
            if file is winner:
                file.recommendation = 'SUGGESTED'
                file.reason = "Sugerido como la mejor versión según tus prioridades."
            else:
                file.recommendation = 'REVIEW'
                file.reason = "Hay una versión potencialmente mejor disponible."