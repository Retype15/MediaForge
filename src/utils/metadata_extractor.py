import ffmpeg # type: ignore
from pathlib import Path
from typing import Dict, Optional
import os
import sys

class MetadataExtractor:
    _ffmpeg_exec = "ffmpeg"
    _ffprobe_exec = "ffprobe"

    @classmethod
    def set_ffmpeg_path(cls, path: str):
        if path and os.path.isdir(path):
            normalized_path = os.path.normpath(path)

            # Determinar el nombre del ejecutable según el SO
            exe_suffix = ".exe" if sys.platform == "win32" else ""
            ffmpeg_exe_name = f"ffmpeg{exe_suffix}"
            ffprobe_exe_name = f"ffprobe{exe_suffix}"

            ffmpeg_exe_path = os.path.join(normalized_path, ffmpeg_exe_name)
            ffprobe_exe_path = os.path.join(normalized_path, ffprobe_exe_name)

            if os.path.exists(ffmpeg_exe_path) and os.path.exists(ffprobe_exe_path):
                cls._ffmpeg_exec = ffmpeg_exe_path
                cls._ffprobe_exec = ffprobe_exe_path
                print(f"FFprobe path set to: {cls._ffprobe_exec}")
            else:
                print(f"Warning: '{ffmpeg_exe_name}' or '{ffprobe_exe_name}' not found in '{normalized_path}'. Using system PATH.")
        else:
            cls._ffmpeg_exec = "ffmpeg"
            cls._ffprobe_exec = "ffprobe"

    @classmethod
    def get_media_info(cls, file_path: Path) -> Optional[Dict]:
        try:
            probe = ffmpeg.probe(str(file_path), cmd=cls._ffprobe_exec)
            
            video_stream = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
            
            if not video_stream:
                return None

            duration = 0.0
            if 'duration' in probe.get('format', {}):
                try: duration = float(probe['format']['duration'])
                except (ValueError, TypeError): pass
            
            if duration == 0.0 and 'duration' in video_stream:
                try: duration = float(video_stream['duration'])
                except (ValueError, TypeError): pass

            return {
                'duration': duration,
                'width': video_stream.get('width', 0),
                'height': video_stream.get('height', 0),
                'v_codec': video_stream.get('codec_name', 'unknown'),
            }
        except ffmpeg.Error as e:
            return None
        except Exception as e:
            return None