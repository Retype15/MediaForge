
---

### **Documento de Diseño y Arquitectura de Software: MediaForge**

**Versión:** 1.0
**Fecha:** 16 de Agosto de 2025
**Autor:** Rety

#### **1. Visión General y Objetivos del Proyecto**

**1.1. Propósito:**
MediaForge es una aplicación de escritorio multiplataforma, construida con Python y PyQt6, diseñada para ayudar a los usuarios a gestionar grandes colecciones de medios digitales (películas, series, etc.). Su función principal es escanear múltiples ubicaciones de almacenamiento, identificar archivos de medios semánticamente duplicados y proporcionar herramientas inteligentes para que el usuario decida qué copias conservar o eliminar, basándose en un sistema de prioridades configurable.

**1.2. Objetivos Clave:**

* **Identificación Inteligente:** Ir más allá de la simple comparación de hashes. El sistema debe entender que `The.Matrix.1999.mkv` y `The Matrix (1999) 4K REMUX.mkv` son el mismo contenido.
* **Personalización del Usuario:** Permitir al usuario definir qué constituye la "mejor" copia de un archivo (mayor calidad, menor tamaño, presencia de un idioma específico de audio/subtítulos).
* **Rendimiento:** Asegurar que la interfaz de usuario permanezca fluida y receptiva en todo momento, delegando las tareas pesadas (escaneo de discos, análisis de metadatos) a hilos de trabajo en segundo plano.
* **Extensibilidad:** Diseñar una arquitectura modular que permita a la comunidad o a desarrolladores futuros crear y añadir nuevos métodos de escaneo, identificación (Matchers) y acciones sin modificar el núcleo de la aplicación.
* **Usabilidad:** Ofrecer una interfaz de usuario clara, intuitiva y con un tema oscuro por defecto para una experiencia visual agradable.
* **Internacionalización:** Soportar múltiples idiomas a través de un sistema de traducción sencillo y escalable.

---

#### **2. Arquitectura del Sistema**

Adoptaremos un patrón de diseño modular y desacoplado, inspirado en Model-View-Controller (MVC) pero adaptado a la naturaleza de una aplicación de escritorio con PyQt.

**2.1. Componentes Principales:**

1. **Core (El Motor):** Lógica de negocio no visual. Gestiona la configuración, la caché, los hilos de trabajo y la orquestación de los módulos.
2. **Modules (La Inteligencia Extensible):** Colección de plugins intercambiables que definen el *cómo* se escanea, se compara y se actúa sobre los archivos.
3. **UI (La Interfaz):** La capa de presentación visual construida con PyQt6. Es responsable de mostrar los datos y capturar las interacciones del usuario. No contiene lógica de negocio.
4. **Utils (Las Herramientas):** Componentes de soporte como el gestor de traducciones y el extractor de metadatos.

**2.2. Diagrama de Flujo de Datos:**

```
[Usuario] -> [UI: MainWindow] --(Inicia Escaneo)--> [Core: AppController]
     ^                                                      |
     |                                                      v
[UI: Muestra Progreso/Resultados] <-----(Señales)---- [Core: ScanWorker (QThread)]
     ^                                                      |
     |                                                      v (Usa Módulos)
     |     [Modules: Scanner] -> [Core: CacheManager] -> [Modules: Matcher] -> [Utils: MetadataExtractor]
     |                                                      |
     |                                                      v (Resultados)
     +------------------------------------------------------+
```

1. El **Usuario** interactúa con la **UI**.
2. La **UI** notifica al **Core** (un controlador principal) para iniciar una acción.
3. El **Core** crea un **Worker** en un hilo separado para no bloquear la UI.
4. El **Worker** utiliza los **Módulos** seleccionados (configurados por el usuario) para realizar la tarea.
    * Usa un `Scanner` para listar archivos.
    * Consulta/actualiza la `CacheManager` (SQLite).
    * Usa un `Matcher` para encontrar duplicados.
    * El `Matcher` puede usar `MetadataExtractor` para obtener información detallada (pistas de audio, subs).
5. El **Worker** emite señales (`pyqtSignal`) para comunicar el progreso y los resultados finales de vuelta a la **UI**.
6. La **UI** actualiza sus widgets en respuesta a estas señales.

---

#### **3. Diseño Detallado de Componentes**

**3.1. Estructura de Datos Clave (`dataclasses`)**

Para mantener la consistencia de los datos a través de la aplicación, usaremos `dataclasses`.

```python
# src/core/models.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, List

@dataclass
class MediaFile:
    path: Path
    size: int
    mtime: float  # Fecha de modificación
    file_hash: Optional[str] = None
    parsed_info: Dict = field(default_factory=dict) # Resultado de PTN (title, year, quality...)
    metadata_info: Dict = field(default_factory=dict) # Resultado de FFprobe (streams, audio_langs...)
    score: int = 0 # Puntuación calculada por el sistema de recomendación
    recommendation: str = 'KEEP' # 'KEEP', 'DELETE', 'REVIEW'
    reason: str = "" # Por qué se hizo esta recomendación

@dataclass
class DuplicateGroup:
    group_id: str # Un ID único, ej. "the_matrix_1999"
    files: List[MediaFile]
    # Se podría añadir un resumen aquí si fuera necesario
```

**3.2. `src/core` - El Motor**

* **`config_manager.py`:**
  * Clase `ConfigManager` usando `QSettings`.
  * Gestionará: `language`, `active_scanner`, `active_matcher`, `selected_paths`, `matcher_priorities` (un diccionario específico para el matcher activo, ej: `{'audio_lang': 'es', 'quality_order': 'desc'}`).
* **`cache_manager.py`:**
  * Clase `CacheManager` que interactúa con una base de datos SQLite (`mediaforge_cache.db`).
  * **Tabla `files`:** `path (PK)`, `size`, `mtime`, `file_hash`, `parsed_info_json`, `metadata_info_json`.
  * **Métodos:** `get_file_data(path)`, `update_file_data(media_file)`, `get_all_files_for_paths(paths)`.
  * **Lógica:** Antes de analizar un archivo, el worker preguntará a la caché. Si `path`, `size` y `mtime` coinciden, usará los datos cacheados. Si no, procesará el archivo y actualizará la caché.
* **`workers.py`:**
  * Clase `WorkerSignals(QObject)` para definir las señales: `progress(int)`, `status_update(str)`, `results_ready(list[DuplicateGroup])`, `finished()`.
  * Clase `ScanWorker(QThread)`:
    * `__init__(self, paths, config)`: Recibe las rutas a escanear y una instantánea de la configuración relevante.
    * `run()`: El corazón del trabajo en segundo plano.
            1. Itera sobre las rutas.
            2. Usa el `Scanner` para obtener la lista de archivos.
            3. Para cada archivo:
                a. Comprueba la caché.
                b. Si es necesario, calcula hash, parsea nombre (`PTN`), y extrae metadatos (`MetadataExtractor`). Esto es la parte más lenta.
                c. Actualiza la caché.
                d. Emite señales de progreso (`status_update`).
            4. Una vez con la lista completa de `MediaFile` objects, la pasa al `Matcher`.
            5. El `Matcher` devuelve los `DuplicateGroup`.
            6. **Lógica de Recomendación:** Dentro del worker, después de obtener los grupos, se itera sobre cada `DuplicateGroup`. Para cada grupo, se aplica la lógica de prioridades (definida por el usuario en `config`) para puntuar cada `MediaFile`. El de mayor puntuación se marca como `KEEP`, el resto como `DELETE`.
            7. Emite la señal `results_ready` con la lista final de grupos.

**3.3. `src/utils` - Herramientas de Soporte**

* **`translator.py`:**
  * Clase `Translator` (Singleton) como se describió anteriormente.
  * Cargará el `es_ES.json` o `en_US.json` de `assets/translations` según la configuración.
* **`metadata_extractor.py`:**
  * **Dependencia CRÍTICA:** `ffmpeg` (ffprobe). El programa deberá incluirlo o guiar al usuario para su instalación. Usaremos la librería `ffmpeg-python` como wrapper.
  * Clase `MetadataExtractor`:
    * Método `get_media_info(file_path)`:
      * Ejecuta `ffprobe` sobre el archivo.
      * Parsea la salida JSON.
      * Devuelve un diccionario estructurado: `{'format': {...}, 'streams': [{'codec_type': 'audio', 'tags': {'language': 'spa'}}, {'codec_type': 'subtitle', 'tags': {'language': 'eng'}}]}`.
      * Manejará errores si `ffprobe` falla o el archivo está corrupto.

**3.4. `src/modules` - La Inteligencia Extensible**

* **`base.py`:**
  * `MatcherBase(ABC)`:
    * `get_name()` -> str: Nombre para la UI.
    * `get_id()` -> str: Identificador único (ej. "media_name_matcher").
    * `find_duplicates(files: List[MediaFile])` -> `List[DuplicateGroup]`: Lógica principal.
    * `get_configurable_priorities()` -> `Dict`: **Método clave**. Devuelve la estructura de opciones que este matcher soporta. La UI usará esto para construir el diálogo de configuración dinámicamente.
      * *Ejemplo de retorno:*

                ```json
                {
                  "quality": {"type": "order", "options": ["4K", "1080p", "720p"], "default": "desc"},
                  "audio_lang": {"type": "select", "options": ["spa", "eng", "jpn"], "default": "spa"},
                  "size": {"type": "choice", "options": ["smallest", "largest"], "default": "largest"}
                }
                ```

* **`matchers/media_name_matcher.py`:**
  * `MediaNameMatcher(MatcherBase)`:
  * `find_duplicates`: Usa `PTN` para parsear `title` y `year` del nombre del archivo. Agrupa archivos con el mismo `title` y `year`.
  * `get_configurable_priorities`: Ofrecerá prioridades basadas en la información del nombre: resolución, códec, fuente (BluRay, WEB-DL).

* **`matchers/metadata_matcher.py` (El avanzado):**
  * `MetadataMatcher(MatcherBase)`:
  * `find_duplicates`: Similar al anterior, pero usa la información de `metadata_info` como fuente principal de verdad si está disponible.
  * `get_configurable_priorities`: Ofrecerá opciones mucho más ricas: "Preferir con audio en Español (spa)", "Preferir con subtítulos en Inglés (eng)", "Preferir códec H.265".

**3.5. `src/ui` - La Interfaz de Usuario**

* **`main_window.py`:**
  * Contendrá la disposición principal: un área para seleccionar rutas, la lista de resultados, una barra de estado y una barra de menú/herramientas.
  * El área de resultados será un `QTreeWidget`:
    * Nodos de primer nivel: Representan un `DuplicateGroup` (ej. "The Matrix (1999) - 3 duplicados encontrados").
    * Nodos hijos: Representan cada `MediaFile` en ese grupo.
    * Columnas: `Recomendación` (icono de check/basura), `Ruta del Archivo`, `Tamaño`, `Calidad`, `Audio`, `Subtítulos`, `Razón`.
  * Conectará las acciones (botones "Escanear", "Aplicar Acciones") a la lógica del Core.
* **`dialogs/settings_dialog.py`:**
  * Diálogo de configuración.
  * Pestañas: General (Idioma), Escaneo, **Matcher**.
  * La pestaña "Matcher" será dinámica:
        1. Un `QComboBox` para seleccionar el `Matcher` activo (`media_name_matcher`, `metadata_matcher`).
        2. Cuando se cambia el `Matcher`, el diálogo llamará a `get_configurable_priorities()` del módulo seleccionado.
        3. Automáticamente, creará los widgets (`QComboBox`, `QCheckBox`, etc.) correspondientes a las prioridades que el `Matcher` expone.
        4. Al guardar, almacena la configuración en `ConfigManager`.

---

#### **4. Desafíos Técnicos y Mitigaciones**

1. **Rendimiento del Escaneo y Análisis:**
    * **Problema:** Escanear discos y, sobre todo, ejecutar `ffprobe` en miles de archivos es extremadamente lento.
    * **Mitigación:**
        * **Multithreading:** Ya contemplado con `QThread`.
        * **Caché Agresiva:** La caché SQLite es fundamental. `ffprobe` solo se ejecutará en archivos nuevos o modificados.
        * **Configuración de "Profundidad":** Ofrecer en la configuración un "Modo de escaneo rápido" (solo nombres de archivo) vs. "Modo de escaneo profundo" (con metadatos), para que el usuario elija.

2. **Precisión del Matching:**
    * **Problema:** Nombres de archivo mal formateados o metadatos incorrectos pueden llevar a agrupaciones erróneas.
    * **Mitigación:**
        * **Lógica Híbrida:** El `Matcher` debe ser robusto. Si el parseo del nombre falla, puede intentar una coincidencia más "difusa" (fuzzy matching). Si los metadatos y el nombre de archivo discrepan, puede marcar el grupo para "Revisión Manual".
        * **Transparencia:** La columna "Razón" en la UI es clave. Debe explicar *por qué* el programa recomienda una acción (ej. "Mayor resolución (1080p > 720p)", "Contiene pista de audio 'spa' preferida").

3. **Dependencia Externa (FFmpeg):**
    * **Problema:** La aplicación depende de `ffmpeg`. Los usuarios no técnicos pueden tener dificultades para instalarlo.
    * **Mitigación:**
        * **Bundling:** La mejor solución es empaquetar los binarios de `ffmpeg` y `ffprobe` junto con la aplicación al crear el ejecutable con `PyInstaller`. Esto aumenta el tamaño del paquete, pero garantiza que funcione "out-of-the-box".
        * **Detección y Guía:** Como alternativa, la aplicación puede buscar `ffmpeg` en el PATH del sistema al inicio. Si no lo encuentra, mostrar un diálogo guiando al usuario para que lo descargue y lo coloque en la carpeta de la aplicación o lo añada al PATH.

---

#### **5. Plan de Desarrollo (Roadmap por Hitos)**

1. **Hito 1: Fundación y Esqueleto (Sprint 1)**
    * [X] Configurar la estructura de directorios del proyecto.
    * [X] Implementar el Singleton `Translator` y crear archivos JSON de idioma básicos.
    * [X] Implementar `ConfigManager` con `QSettings`.
    * [X] Crear la `MainWindow` básica con menú, barra de estado y un widget central vacío. Aplicar tema oscuro.
    * [X] Crear el `SettingsDialog` básico para cambiar de idioma.

2. **Hito 2: El Núcleo de Escaneo (Sprint 2)**
    * [X] Implementar el `CacheManager` con la estructura de la base de datos SQLite.
    * [X] Definir las `dataclasses` `MediaFile` y `DuplicateGroup`.
    * [X] Crear el `ScanWorker` y la clase de señales.
    * [X] Implementar la lógica de escaneo de archivos (usando `pathlib`) y la interacción con la caché (sin análisis de metadatos aún).
    * [X] Conectar el botón "Escanear" para que inicie el worker y muestre el progreso en una `QProgressBar` y mensajes en la barra de estado.

3. **Hito 3: Primer Matcher y Visualización (Sprint 3)**
    * [X] Definir la interfaz `MatcherBase`.
    * [X] Implementar `MediaNameMatcher` usando `parse-torrent-name` (PTN).
    * [X] Integrar el `Matcher` en el `ScanWorker`.
    * [X] Implementar el `QTreeWidget` en la `MainWindow` para mostrar los `DuplicateGroup` y `MediaFile` devueltos por el worker.
    * [X] Implementar la lógica de recomendación básica basada en prioridades simples (ej. mayor resolución parseada del nombre).

4. **Hito 4: Metadatos y Matcher Avanzado (Sprint 4)**
    * [X] Implementar el `MetadataExtractor` como un wrapper robusto para `ffprobe`.
    * [X] Integrar la llamada al extractor en el `ScanWorker` (controlado por una opción de configuración).
    * [X] Implementar el `MetadataMatcher`, que prioriza la información de los metadatos.
    * [X] Implementar la lógica de recomendación avanzada que utiliza las pistas de audio/subtítulos.

5. **Hito 5: Configuración Dinámica y Acciones (Sprint 5)**
    * [X] Implementar la lógica en el `SettingsDialog` para que genere dinámicamente los controles de prioridad basándose en el `get_configurable_priorities()` del `Matcher` seleccionado.
    * [X] Añadir botones de acción en la UI ("Eliminar seleccionados", "Mover a...").
    * [X] Implementar la lógica para ejecutar estas acciones de forma segura (ej. mover a la papelera de reciclaje en lugar de borrar permanentemente, usando una librería como `send2trash`).

6. **Hito 6: Pulido, Pruebas y Empaquetado (Sprint 6)**
    * [X] Refinar la interfaz: añadir iconos, tooltips, mejorar el layout.
    * [X] Realizar pruebas exhaustivas con grandes colecciones de medios y casos borde.
    * [X] Escribir la documentación para el usuario (README).
    * [X] Crear el script de `PyInstaller` para empaquetar la aplicación, incluyendo `ffmpeg` y los assets.

---
