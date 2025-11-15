# Flujo interno del anonimizador

Este documento resume, con referencias al código fuente, cada etapa crítica del procesamiento descrito en `anonimizador v.5.py`.

## 1. Configuración y logging

1. Se combinan los valores por defecto, `config.yaml` y las variables de entorno (`load_config`, líneas 87-110).  
2. La GUI puede guardar o recargar configuraciones mediante `save_config`/`load_config` (`anonimizador v.5.py:112`, `anonimizador v.5.py:1049`).  
3. Cada corrida crea un `RunLogger` que escribe un `.jsonl` con métricas por chunk y un `.json` resumen (`anonimizador v.5.py:134-169`).  
4. `resolve_logs_dir` fuerza rutas absolutas para esos archivos (`anonimizador v.5.py:127-131`).

## 2. Preparación del documento

1. `run_anonymization` inicializa el contexto, fabrica rutas de salida y valida configuraciones (`anonimizador v.5.py:629-666`).  
2. `LMStudioClient.check_health` consulta `/models` para asegurar que el servidor está disponible (`anonimizador v.5.py:212-220`).  
3. Según la extensión, se usa `extract_text_from_pdf` o `extract_text_from_docx` para obtener texto plano (`anonimizador v.5.py:290-303`).  
4. Se aborta si no se extrajo contenido (`anonimizador v.5.py:687-688`).

## 3. Tokenización y troceo

1. `tokenize_with_spans` recorre el texto con una regex que conserva espacios y registra offsets (`anonimizador v.5.py:308-325`).  
2. `build_chunks` corta el documento en fragmentos contiguos de `max_context_tokens * safety_factor`, rechaza solapamientos y garantiza continuidad con `validate_chunk_sequence` (`anonimizador v.5.py:328-391`).  
3. Cada `Chunk` almacena índices de caracteres/tokens y utilidades como `preview` para logs (`anonimizador v.5.py:268-285`).

## 4. Procesamiento de chunks

1. El `SYSTEM_PROMPT` define reglas estrictas y placeholders permitidos; el prompt del usuario es el texto del chunk (`anonimizador v.5.py:396-435`).  
2. `process_chunks` itera secuencialmente, llama a `LMStudioClient.generate` (determinista, con reintentos y backoff) y registra métricas/duración por fragmento (`anonimizador v.5.py:171-259`, `anonimizador v.5.py:437-516`).  
3. El modo debug guarda entrada y salida completas en el log, y `abort_on_failure` permite cortar la corrida si algún chunk falla (`anonimizador v.5.py:446-469`).

## 5. Fusión y validación

1. `merge_chunks` recompone el documento usando los offsets para evitar solapamientos; luego se escribe `*_anonimizado.txt` (`anonimizador v.5.py:529-548`, `anonimizador v.5.py:712-714`).  
2. `calculate_length_metrics` calcula delta/ratio y `generate_diff_report` crea `*_comparacion.html` (`anonimizador v.5.py:552-582`, `anonimizador v.5.py:729-734`).  
3. `detect_suspicious_edits` usa `SequenceMatcher` para reportar reemplazos o omisiones inesperadas, alimentando el bloque `validation` del resumen (`anonimizador v.5.py:586-623`, `anonimizador v.5.py:736-757`).  
4. `RunLogger.finalize` agrega todos los datos al `run_summary_<id>.json` (`anonimizador v.5.py:161-169`).

## 6. GUI y orquestación

1. `AnonymizerApp` monta pestañas para procesamiento, configuración, registros y “Acerca de”, cargando la configuración al inicio (`anonimizador v.5.py:788-1048`).  
2. `_start_processing` valida el archivo, toma la configuración del formulario y lanza `run_anonymization` en un hilo con callbacks para progreso y logs (`anonimizador v.5.py:1111-1184`).  
3. `_process_log_queue` refresca la UI cada 200 ms, muestra el resumen final, abre popups ante errores y permite abrir la carpeta de logs (`anonimizador v.5.py:1186-1289`).  
4. El resumen en la pestaña “Procesamiento” lista métricas clave, advertencias de validación y las rutas de salida (`anonimizador v.5.py:1230-1271`).
