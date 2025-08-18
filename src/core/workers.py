import os
import json
from pathlib import Path
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from src.modules.base import ScannerBase, MatcherBase
from src.core.models import MediaFile
from src.utils.metadata_extractor import MetadataExtractor
from src.utils.text_parser import robust_parse_episode, standardize_text
from src.core.cache_manager import CacheManager
from src.core.recommender import Recommender
from src.core.config_manager import ConfigManager

import re
from typing import Optional, Tuple, List, Dict, Set
from collections import defaultdict

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
        """
        Orquesta el proceso completo de escaneo, desde la recolección de archivos hasta
        la emisión de los resultados, dividido en fases lógicas.
        """
        cache = CacheManager()
        config = ConfigManager()
        priority_order = config.get("recommendation/priority_order", [])
        recommender = Recommender(priority_order)
        ignore_list = cache.get_ignore_list()
        
        try:
            # --- FASE 1: Recolectar archivos y comparar con la caché ---
            self.signals.status_update.emit("Fase 1: Recolectando y comparando archivos con la caché...")
            self.signals.set_progress_bar_indeterminate.emit(True)
            
            unchanged_from_cache, files_to_process_map = self._collect_and_compare_files(cache)
            if not self._is_running: self.stop_gracefully(); return

            # --- FASE 2: Procesar archivos nuevos/modificados y actualizar la caché ---
            self.signals.set_progress_bar_indeterminate.emit(False)
            processed_files = self._process_file_list(list(files_to_process_map.keys()))
            if not self._is_running: self.stop_gracefully(); return

            self._update_cache_with_new_files(cache, processed_files, files_to_process_map)
            
            # --- FASE 3: Identificar duplicados, filtrar y aplicar recomendaciones ---
            all_media_files_final = unchanged_from_cache + processed_files
            
            self.signals.status_update.emit(f"Fase final: Identificando duplicados en {len(all_media_files_final)} archivos...")
            self.signals.progress.emit(100)
            
            duplicate_structure = self._find_and_process_duplicates(all_media_files_final, recommender, ignore_list)
            
            if self._is_running:
                self.signals.results_ready.emit(duplicate_structure)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.signals.error.emit(f"Ha ocurrido un error inesperado en el worker: {e}")
        finally:
            cache.close()
            self.signals.finished.emit()
            
    def _collect_and_compare_files(self, cache: CacheManager) -> Tuple[List[MediaFile], Dict[Path, str]]:
        """
        Recorre las rutas de escaneo, las compara con la caché y devuelve dos colecciones:
        - Una lista de MediaFiles que no han cambiado y se pueden usar directamente.
        - Un diccionario de archivos nuevos o modificados que necesitan ser procesados.
        """
        unchanged_files = []
        files_to_process_map = {}
        
        for i, scan_path in enumerate(self.paths_to_scan):
            if not self._is_running: break
            self.signals.status_update.emit(f"Verificando ruta ({i+1}/{len(self.paths_to_scan)}): {scan_path}...")

            # Manejar rutas desconectadas o no existentes
            if not scan_path.exists() or not scan_path.is_dir():
                cached_files = cache.get_files_for_path(str(scan_path))
                unchanged_files.extend(cached_files.values())
                continue

            # Sincronizar caché con el disco
            volume_name = scan_path.drive if scan_path.drive else str(scan_path.parts[0])
            cache.update_scan_path(str(scan_path), volume_name)
            
            files_on_disk = set(self.scanner.scan(scan_path))
            cached_files_map = cache.get_files_for_path(str(scan_path))
            
            # Eliminar de la caché archivos que ya no existen en el disco
            files_to_remove_from_cache = [str(p) for p in (set(cached_files_map.keys()) - files_on_disk)]
            if files_to_remove_from_cache:
                cache.remove_files_batch(files_to_remove_from_cache)
            
            # Comparar cada archivo en el disco con su entrada en la caché
            for path in files_on_disk:
                cached_file = cached_files_map.get(path)
                if cached_file:
                    try:
                        stats = path.stat()
                        if stats.st_size != cached_file.size or stats.st_mtime != cached_file.mtime:
                            files_to_process_map[path] = str(scan_path) # Modificado
                        else:
                            unchanged_files.append(cached_file) # Sin cambios
                    except FileNotFoundError: pass
                else:
                    files_to_process_map[path] = str(scan_path) # Nuevo

        return unchanged_files, files_to_process_map

    def _update_cache_with_new_files(self, cache: CacheManager, processed_files: List[MediaFile], files_to_process_map: Dict[Path, str]):
        """Actualiza la caché con los archivos que acaban de ser procesados."""
        if not processed_files:
            return
            
        files_to_cache_by_path = defaultdict(list)
        for file in processed_files:
            scan_path_str = files_to_process_map.get(file.path)
            if scan_path_str:
                files_to_cache_by_path[scan_path_str].append(file)
        
        for scan_path_str, files_list in files_to_cache_by_path.items():
            cache.update_files_batch(scan_path_str, files_list)

    def _find_and_process_duplicates(self, all_files: List[MediaFile], recommender: Recommender, ignore_list: Set[str]) -> Dict:
        """
        Ejecuta el matcher, filtra los duplicados según la lista de ignorados
        y aplica las recomendaciones de prioridad.
        """
        # Encontrar duplicados
        duplicate_structure = self.matcher.find_duplicates(all_files)
        
        # Filtrar por lista de ignorados
        filtered_series = {}
        for series_title, episodes in duplicate_structure.get("series", {}).items():
            series_id = standardize_text(series_title)
            if series_id in ignore_list: continue
            valid_episodes = [group for group in episodes if f"{series_id}/{group.group_id}" not in ignore_list]
            if valid_episodes: filtered_series[series_title] = valid_episodes
        duplicate_structure["series"] = filtered_series

        filtered_movies = [group for group in duplicate_structure.get("movies", []) if standardize_text(group.display_title) not in ignore_list]
        duplicate_structure["movies"] = filtered_movies
        
        # Aplicar recomendaciones
        self.signals.status_update.emit("Aplicando recomendaciones...")
        for series_title, duplicate_episodes in duplicate_structure.get("series", {}).items():
            for group in duplicate_episodes:
                recommender.apply_recommendations(group)
        for movie_group in duplicate_structure.get("movies", []):
            recommender.apply_recommendations(movie_group)
        
        return duplicate_structure

    def _process_file_list(self, files_to_process: List[Path]) -> List[MediaFile]:
        """
        Procesa una lista de archivos, extrayendo metadatos y parseando información.
        Emite señales de progreso durante la operación.
        """
        processed = []
        total = len(files_to_process)
        if total == 0: return []
        
        self.signals.status_update.emit(f"Fase 2: Procesando {total} archivos nuevos/modificados...")
        
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
