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
from collections import defaultdict
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
    set_progress_bar_indeterminate = pyqtSignal(bool)
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
            # --- INICIO DE CORRECCIÓN: NUEVA LÓGICA DE BUCLE ---
            
            # Fase 1: Recolección Inteligente
            self.signals.status_update.emit("Fase 1: Recolectando archivos...")
            self.signals.set_progress_bar_indeterminate.emit(True)
            self.signals.progress.emit(0)

            all_media_files_from_cache: List[MediaFile] = []
            files_to_process_map: Dict[Path, str] = {} # Mapeo de archivo a su scan_path
            
            for i, scan_path in enumerate(self.paths_to_scan):
                if not self._is_running: break
                self.signals.status_update.emit(f"Verificando ruta ({i+1}/{len(self.paths_to_scan)}): {scan_path}...")

                if not scan_path.exists() or not scan_path.is_dir():
                    self.signals.status_update.emit(f"Ruta offline. Usando caché para {scan_path}...")
                    cached_files = cache.get_files_for_path(str(scan_path))
                    all_media_files_from_cache.extend(cached_files.values())
                    continue

                files_on_disk = set(self.scanner.scan(scan_path))
                cached_files_map = cache.get_files_for_path(str(scan_path))
                
                files_to_remove_from_cache = [str(p) for p in (set(cached_files_map.keys()) - files_on_disk)]
                if files_to_remove_from_cache:
                    cache.remove_files_batch(files_to_remove_from_cache)
                
                for path in files_on_disk:
                    if path in cached_files_map:
                        try:
                            stats = path.stat()
                            cached_file = cached_files_map[path]
                            
                            if stats.st_size != cached_file.size or stats.st_mtime != cached_file.mtime:
                                files_to_process_map[path] = str(scan_path)
                            else:
                                all_media_files_from_cache.append(cached_file)
                        except FileNotFoundError:
                            pass # Será borrado en el próximo escaneo de esta ruta
                    else: # Es un archivo nuevo
                        files_to_process_map[path] = str(scan_path)

            if not self._is_running: self.stop_gracefully(); return

            # Fase 2: Procesamiento en Lote (una sola vez)
            self.signals.set_progress_bar_indeterminate.emit(False)
            processed_files = self._process_file_list(list(files_to_process_map.keys()))
            
            # Fase 3: Actualización de la Caché
            if processed_files:
                # Agrupar por scan_path para la actualización en lote
                files_to_cache_by_path = defaultdict(list)
                for file in processed_files:
                    scan_path_str = files_to_process_map.get(file.path)
                    if scan_path_str:
                        files_to_cache_by_path[scan_path_str].append(file)
                
                for scan_path_str, files_list in files_to_cache_by_path.items():
                    cache.update_files_batch(scan_path_str, files_list)

            # Actualizar timestamps de las rutas escaneadas
            for scan_path in self.paths_to_scan:
                 if scan_path.exists():
                    volume_name = scan_path.drive if scan_path.drive else str(scan_path.parts[0])
                    cache.update_scan_path(str(scan_path), volume_name)

            if not self._is_running: self.stop_gracefully(); return
            
            # Unir las listas para el análisis final
            all_media_files_final = all_media_files_from_cache + processed_files

            # --- FIN DE CORRECCIÓN ---
            
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

            filtered_movies = []
            for movie_group in duplicate_structure.get("movies", []):
                movie_id = standardize_text(movie_group.display_title)
                if movie_id not in ignore_list:
                    filtered_movies.append(movie_group)
            duplicate_structure["movies"] = filtered_movies

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