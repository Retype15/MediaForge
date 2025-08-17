import sqlite3
import json
import time
from pathlib import Path
from typing import List, Dict, Set
from src.core.models import MediaFile

DB_FILE = "mediaforge_cache.db"

class CacheManager:
    def __init__(self, db_path=DB_FILE):
        self.conn = sqlite3.connect(db_path)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scanned_paths (
                path TEXT PRIMARY KEY,
                volume_name TEXT,
                last_scanned INTEGER
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS media_files (
                file_path TEXT PRIMARY KEY,
                scan_path TEXT,
                size INTEGER,
                mtime REAL,
                parsed_info_json TEXT,
                metadata_info_json TEXT,
                FOREIGN KEY (scan_path) REFERENCES scanned_paths (path) ON DELETE CASCADE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ignore_list (
                ignore_key TEXT PRIMARY KEY,
                ignore_level TEXT,
                date_added INTEGER
            )
        ''')
        self.conn.commit()

    def get_scanned_paths(self) -> List[dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT path, volume_name, last_scanned FROM scanned_paths ORDER BY last_scanned DESC")
        return [{"path": row[0], "volume_name": row[1], "last_scanned": row[2]} for row in cursor.fetchall()]

    def update_scan_path(self, path: str, volume_name: str):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO scanned_paths (path, volume_name, last_scanned) VALUES (?, ?, ?)",
            (path, volume_name, int(time.time()))
        )
        self.conn.commit()
    
    def remove_scan_path(self, path: str):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM scanned_paths WHERE path = ?", (path,))
        self.conn.commit()


    def get_files_for_path(self, scan_path: str) -> Dict[Path, MediaFile]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT file_path, size, mtime, parsed_info_json, metadata_info_json FROM media_files WHERE scan_path = ?",
            (scan_path,)
        )
        cached_files = {}
        for row in cursor.fetchall():
            file_path, size, mtime, parsed_json, meta_json = row
            p_path = Path(file_path)
            cached_files[p_path] = MediaFile(
                path=p_path,
                size=size,
                mtime=mtime,
                parsed_info=json.loads(parsed_json) if parsed_json else {},
                metadata_info=json.loads(meta_json) if meta_json else {}
            )
        return cached_files

    def update_files_batch(self, scan_path: str, files: List[MediaFile]):
        cursor = self.conn.cursor()
        data_to_insert = []
        for file in files:
            data_to_insert.append((
                str(file.path),
                scan_path,
                file.size,
                file.mtime,
                json.dumps(file.parsed_info),
                json.dumps(file.metadata_info) if file.metadata_info else None
            ))
        
        cursor.executemany(
            "INSERT OR REPLACE INTO media_files (file_path, scan_path, size, mtime, parsed_info_json, metadata_info_json) VALUES (?, ?, ?, ?, ?, ?)",
            data_to_insert
        )
        self.conn.commit()

    def remove_files_batch(self, file_paths: List[str]):
        if not file_paths: return
        cursor = self.conn.cursor()
        placeholders = ','.join(['?'] * len(file_paths))
        cursor.execute(f"DELETE FROM media_files WHERE file_path IN ({placeholders})", file_paths)
        self.conn.commit()

    def add_to_ignore_list(self, key: str, level: str):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO ignore_list (ignore_key, ignore_level, date_added) VALUES (?, ?, ?)",
            (key, level, int(time.time()))
        )
        self.conn.commit()

    def get_ignore_list(self) -> Set[str]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT ignore_key FROM ignore_list")
        return {row[0] for row in cursor.fetchall()}

    def close(self):
        self.conn.close()