import os
import json
from pathlib import Path
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from src.modules.base import ScannerBase, MatcherBase
from src.core.models import MediaFile
from src.utils.metadata_extractor import MetadataExtractor
from src.core.cache_manager import CacheManager
from src.core.recommender import Recommender
from src.core.config_manager import ConfigManager
import re
from typing import Optional, Tuple, List

# Requerido por el worker para el parseo inicial antes de cachear
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

class WorkerSignals(QObject):
    progress = pyqtSignal(int)
    status_update = pyqtSignal(str)
    finished = pyqtSignal()
    results_ready = pyqtSignal(dict)
    error = pyqtSignal(str)

class ScanWorker(QThread):
    def __init__(self, paths: list, scanner: ScannerBase, matcher: MatcherBase):
        super().__init__()
        self.signals = WorkerSignals()
        self.paths_to_scan = [Path(p) for p in paths]
        self.scanner = scanner
        self.matcher = matcher
        self._is_running = True

    def run(self):
        cache = CacheManager()
        config = ConfigManager()
        priority_order = config.get("recommendation/priority_order", [])
        recommender = Recommender(priority_order)
        ignore_list = cache.get_ignore_list()
        
        try:
            all_media_files_final = []
            for scan_path in self.paths_to_scan:
                if not self._is_running: break
                self.signals.status_update.emit(f"Verificando ruta: {scan_path}...")
                
                volume_name = "Offline"
                try:
                    volume_name = scan_path.drive if scan_path.drive else str(scan_path.parts[0])
                except Exception: pass

                if not scan_path.exists() or not scan_path.is_dir():
                    self.signals.status_update.emit(f"Ruta offline. Usando caché para {scan_path}...")
                    cached_files = cache.get_files_for_path(str(scan_path))
                    all_media_files_final.extend(cached_files.values())
                    continue

                files_on_disk = set(self.scanner.scan(scan_path))
                cached_files_map = cache.get_files_for_path(str(scan_path))
                
                files_to_remove_from_cache = [str(p) for p in (set(cached_files_map.keys()) - files_on_disk)]
                files_to_check = files_on_disk.intersection(set(cached_files_map.keys()))
                files_to_process = list(files_on_disk - set(cached_files_map.keys()))
                
                for path in files_to_check:
                    try:
                        stats = path.stat()
                        cached_file = cached_files_map[path]
                        if stats.st_size != cached_file.size or stats.st_mtime != cached_file.mtime:
                            files_to_process.append(path)
                        else:
                            all_media_files_final.append(cached_file)
                    except FileNotFoundError:
                        files_to_remove_from_cache.append(str(path))

                processed_files = self._process_file_list(files_to_process)
                all_media_files_final.extend(processed_files)

                if processed_files: cache.update_files_batch(str(scan_path), processed_files)
                if files_to_remove_from_cache: cache.remove_files_batch(files_to_remove_from_cache)
                cache.update_scan_path(str(scan_path), volume_name)

            if not self._is_running: self.stop_gracefully(); return
            
            self.signals.status_update.emit(f"Fase final: Identificando duplicados en {len(all_media_files_final)} archivos...")
            self.signals.progress.emit(100)
            
            duplicate_structure = self.matcher.find_duplicates(all_media_files_final)
            
            filtered_series = {}
            for series_title, episodes in duplicate_structure.get("series", {}).items():
                series_id = standardize_text(series_title)
                if series_id in ignore_list: continue
                
                valid_episodes = []
                for group in episodes:
                    episode_id = f"{series_id}/{group.group_id}"
                    if episode_id not in ignore_list:
                        valid_episodes.append(group)
                
                if valid_episodes:
                    filtered_series[series_title] = valid_episodes
            duplicate_structure["series"] = filtered_series

            self.signals.status_update.emit("Aplicando recomendaciones...")
            for series_title, duplicate_episodes in duplicate_structure.get("series", {}).items():
                for group in duplicate_episodes:
                    recommender.apply_recommendations(group)
            for movie_group in duplicate_structure.get("movies", []):
                recommender.apply_recommendations(movie_group)
            
            if self._is_running:
                self.signals.results_ready.emit(duplicate_structure)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.signals.error.emit(f"Ha ocurrido un error inesperado en el worker: {e}")
        finally:
            cache.close()
            self.signals.finished.emit()

    def _process_file_list(self, files_to_process: List[Path]) -> List[MediaFile]:
        processed = []
        total = len(files_to_process)
        if total == 0: return []
        for i, file_path in enumerate(files_to_process):
             if not self._is_running: break
             self.signals.status_update.emit(f"Procesando ({i+1}/{total}): {file_path.name}")
             self.signals.progress.emit(int(((i+1)/total)*100))
             try:
                stats = file_path.stat()
                metadata = MetadataExtractor.get_media_info(file_path)
                ep_info = robust_parse_episode(file_path.name)
                parsed_info = {}
                if ep_info:
                    parsed_info['season'], parsed_info['episode'] = ep_info
                media_file = MediaFile(
                    path=file_path, size=stats.st_size, mtime=stats.st_mtime,
                    parsed_info=parsed_info, metadata_info=metadata
                )
                processed.append(media_file)
             except FileNotFoundError: continue
        return processed
    
    def stop_gracefully(self):
        self.signals.status_update.emit("Escaneo cancelado por el usuario.")

    def stop(self):
        self.signals.status_update.emit("Cancelando...")
        self._is_running = False