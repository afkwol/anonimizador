# Flujo interno del anonimizador

Este documento resume, con referencias al código fuente, cada etapa crítica del procesamiento descrito en `anonimizador v.5.py`.

### Prerrequisitos y supuestos

- **Entorno**: Python 3.9+ (probado en Windows) con las dependencias de `requirements.txt`. La GUI usa `tkinter`, por lo que conviene instalar Python oficial si falta la librería (`README.md`).
- **Servidor LM Studio**: Debe estar en ejecución con el servidor local activo (`Start Server`). `LMStudioClient.check_health` consulta `GET /models` (`anonimizador v.5.py:212-220`), así que ese endpoint debe responder en `base_url`.
- **Modelos/formatos**: El pipeline espera modelos chat compatibles con `/chat/completions` y archivos de entrada `.pdf`, `.doc` o `.docx`. Otros formatos disparan un `ValueError` temprano (`anonimizador v.5.py:666-699`).

## 1. Configuración y logging

1. Se combinan los valores por defecto, `config.yaml` y las variables de entorno (`load_config`, líneas 87-110).  
2. La GUI puede guardar o recargar configuraciones mediante `save_config`/`load_config` (`anonimizador v.5.py:112`, `anonimizador v.5.py:1049`).  
3. Cada corrida crea un `RunLogger` que escribe un `.jsonl` con métricas por chunk y un `.json` resumen (`anonimizador v.5.py:134-169`).  
4. `resolve_logs_dir` fuerza rutas absolutas para esos archivos (`anonimizador v.5.py:127-131`).
5. Orden de precedencia: `DEFAULT_CONFIG` → `config.yaml` → variables de entorno definidas en `ENV_OVERRIDE_MAP`. Cada override debe parsearse correctamente (ej.: `LM_CHUNK_MAX_TOKENS=3000`), de lo contrario `load_config` devuelve un `ValueError` con el nombre de la variable.

| Clave (ruta)              | Tipo      | Valor por defecto                | Uso principal |
|---------------------------|-----------|----------------------------------|---------------|
| `lm_api.base_url`         | string    | `http://127.0.0.1:1234/v1`       | Endpoint de LM Studio; usado en `/models` y `/chat/completions`. |
| `lm_api.model`            | string    | `granite-3.1-8b-instruct`        | Nombre exacto que expone LM Studio. |
| `chunking.max_context_tokens` | entero | `2500`                           | Tamaño bruto del contexto; luego se escala por `safety_factor`. |
| `chunking.safety_factor`  | float     | `0.85`                           | Reduce `max_context_tokens` para reservar margen al prompt del sistema. |
| `inference.max_tokens`    | entero    | `1024`                           | Límite de tokens generados por chunk (llega tal cual al endpoint). |
| `runtime.max_retries`     | entero    | `2`                              | Cantidad de reintentos de `LMStudioClient.generate` antes de abortar. |
| `runtime.logs_dir`        | ruta      | `./logs`                         | Directorio para los `.jsonl/.json`; se vuelve absoluto con `resolve_logs_dir`. |
| `runtime.abort_on_failure`| booleano  | `false`                          | Si es `true`, `process_chunks` corta en el primer chunk fallido. |

> La pestaña “Configuración” refleja estas claves como formularios, incluyendo `stop_sequences` (uno por línea) y flags como `debug`.

## 2. Preparación del documento

1. `run_anonymization` inicializa el contexto, fabrica rutas de salida y valida configuraciones (`anonimizador v.5.py:629-666`).  
2. `LMStudioClient.check_health` consulta `/models` para asegurar que el servidor está disponible (`anonimizador v.5.py:212-220`).  
3. Según la extensión, se usa `extract_text_from_pdf` o `extract_text_from_docx` para obtener texto plano (`anonimizador v.5.py:290-303`).  
4. Se aborta si no se extrajo contenido (`anonimizador v.5.py:687-688`).  
5. Errores de lectura (archivo inexistente, formato no soportado, PDF sin texto) levantan excepciones que se capturan en `run_anonymization`: el `RunLogger` marca la corrida como `status="error"`, preserva cualquier archivo parcial y deja trazas en `run_summary_<id>.json` para depuración (`anonimizador v.5.py:700-767`).

## 3. Tokenización y troceo

1. `tokenize_with_spans` recorre el texto con una regex que conserva espacios y registra offsets (`anonimizador v.5.py:308-325`).  
2. `build_chunks` corta el documento en fragmentos contiguos de `max_context_tokens * safety_factor`, rechaza solapamientos y garantiza continuidad con `validate_chunk_sequence` (`anonimizador v.5.py:328-391`).  
3. Cada `Chunk` almacena índices de caracteres/tokens y utilidades como `preview` para logs (`anonimizador v.5.py:268-285`).  
4. El algoritmo puede visualizarse como:

```text
token_spans = tokenize(text)
for token_start in range(0, total_tokens, effective_chunk_tokens):
    token_end = min(token_start + effective_chunk_tokens, total_tokens)
    char_start = token_spans[token_start].start
    char_end   = token_spans[token_end-1].end
    yield Chunk(text[char_start:char_end], offsets)
```

Con esto se preserva el mapeo “token → offset” para reconstruir sin huecos. `overlap_tokens` se fuerza a `0` porque los offsets se usan como ventanas cerradas; cualquier superposición rompería `merge_chunks`.

## 4. Procesamiento de chunks

1. El `SYSTEM_PROMPT` define reglas estrictas y placeholders permitidos; el prompt del usuario es el texto del chunk (`anonimizador v.5.py:396-435`).  
2. `process_chunks` itera secuencialmente, llama a `LMStudioClient.generate` (determinista, con reintentos y backoff) y registra métricas/duración por fragmento (`anonimizador v.5.py:171-259`, `anonimizador v.5.py:437-516`).  
3. El modo debug guarda entrada y salida completas en el log, y `abort_on_failure` permite cortar la corrida si algún chunk falla (`anonimizador v.5.py:446-469`).  
4. Cada llamada a `LMStudioClient.generate` usa `timeout=120s` y `max_retries` con retroceso lineal (`retry_backoff_seconds`). Si todos los intentos fallan, se registra `failed_chunks`, la GUI recibe un mensaje de error y el resumen final queda en `status="error"` manteniendo el historial en `run_<id>.jsonl`.

## 5. Fusión y validación

1. `merge_chunks` recompone el documento usando los offsets para evitar solapamientos; luego se escribe `*_anonimizado.txt` (`anonimizador v.5.py:529-548`, `anonimizador v.5.py:712-714`).  
2. `calculate_length_metrics` calcula delta/ratio y `generate_diff_report` crea `*_comparacion.html` (`anonimizador v.5.py:552-582`, `anonimizador v.5.py:729-734`).  
3. `detect_suspicious_edits` usa `SequenceMatcher` para reportar reemplazos u omisiones inesperadas y corta la lista tras `max_items=10`. Se ignoran cambios que sólo contienen placeholders definidos en `PLACEHOLDER_TOKENS`. El resultado alimenta el bloque `validation` del resumen (`anonimizador v.5.py:586-623`, `anonimizador v.5.py:736-757`).  
4. `RunLogger.finalize` agrega todos los datos al `run_summary_<id>.json` (`anonimizador v.5.py:161-169`).

## 6. GUI y orquestación

1. `AnonymizerApp` monta pestañas para procesamiento, configuración, registros y “Acerca de”, cargando la configuración al inicio (`anonimizador v.5.py:788-1048`).  
2. `_start_processing` valida el archivo, toma la configuración del formulario y lanza `run_anonymization` en un hilo con callbacks para progreso y logs (`anonimizador v.5.py:1111-1184`).  
3. `_process_log_queue` refresca la UI cada 200 ms, muestra el resumen final, abre popups ante errores y permite abrir la carpeta de logs (`anonimizador v.5.py:1186-1289`).  
4. El resumen en la pestaña “Procesamiento” lista métricas clave, advertencias de validación y las rutas de salida (`anonimizador v.5.py:1230-1271`).

## Salidas de cada corrida

| Artefacto | Ubicación | Contenido |
|-----------|-----------|-----------|
| `*_anonimizado.txt` | Mismo directorio que el archivo fuente | Texto anonymizado lineal, sin formato. |
| `*_comparacion.html` | Junto al archivo fuente | Tabla HTML con diferencias resaltadas (`HtmlDiff`). |
| `logs/run_<id>.jsonl` | `runtime.logs_dir` | Entradas por chunk (duración, token count, resultados, errores). |
| `logs/run_summary_<id>.json` | `runtime.logs_dir` | Resumen global: estado, métricas de longitud, issues de validación, rutas y tiempos. |

> Incluso cuando ocurre un error, la sección `summary.status` refleja el fallo y `failed_chunks` lista los índices afectados, lo que facilita reintentos controlados desde la GUI.
