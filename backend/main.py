"""
FastAPI Backend para Anonimizador Judicial
"""
import os
import uuid
import tempfile
import logging
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime, timedelta

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from document_processor import process_document, rebuild_document
from anonimizador import (
    extract_entities,
    validate_extraction,
    anonymize_text
)

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuración
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".docx", ".doc", ".rtf"}
TMP_DIR = Path("/tmp/anonimizador")
TMP_DIR.mkdir(exist_ok=True)

# Almacenamiento temporal de archivos procesados (file_id -> metadata)
processed_files: Dict[str, dict] = {}

app = FastAPI(
    title="Anonimizador Judicial",
    description="API para anonimizar documentos judiciales",
    version="2.0.0"
)

# Configurar CORS para desarrollo local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir archivos estáticos del frontend
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")


@app.get("/")
async def root():
    """Redirigir al frontend"""
    return FileResponse(str(frontend_path / "index.html"))


@app.get("/health")
async def health_check():
    """Verificar estado de la API"""
    return {
        "status": "ok",
        "llm_endpoint": os.getenv("OPENAI_API_BASE", "not_configured")
    }


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Endpoint para subir y procesar documento

    Pipeline completo:
    1. Guardar archivo temporal
    2. Extraer texto con document_processor
    3. Extraer entidades con LLM
    4. Validar extracción
    5. Anonimizar texto
    6. Reconstruir documento
    7. Retornar file_id y metadata (warnings, cambios)

    Args:
        file: Documento judicial (.docx, .doc, .rtf)

    Returns:
        JSON con file_id, warnings y metadata
    """
    start_time = datetime.now()
    file_id = str(uuid.uuid4())

    logger.info(f"[{file_id}] Iniciando procesamiento de: {file.filename}")

    # Validar extensión
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        logger.warning(f"[{file_id}] Formato no soportado: {file_ext}")
        raise HTTPException(
            status_code=400,
            detail=f"Formato no soportado. Use: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Validar tamaño
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        logger.warning(f"[{file_id}] Archivo demasiado grande: {len(content)} bytes")
        raise HTTPException(
            status_code=413,
            detail=f"Archivo demasiado grande. Máximo: {MAX_FILE_SIZE / (1024*1024):.0f}MB"
        )

    # Guardar archivo temporal en /tmp
    input_path = TMP_DIR / f"{file_id}_input{file_ext}"
    with open(input_path, "wb") as f:
        f.write(content)

    logger.info(f"[{file_id}] Archivo guardado en: {input_path}")

    warnings: List[str] = []
    entities_count = 0

    try:
        # Paso 1: Extraer texto del documento
        logger.info(f"[{file_id}] Extrayendo texto del documento...")
        text, doc_format = process_document(input_path)
        logger.info(f"[{file_id}] Texto extraído: {len(text)} caracteres, formato: {doc_format}")

        # Paso 2: Extraer entidades con LLM
        logger.info(f"[{file_id}] Extrayendo entidades sensibles con LLM...")
        entities_json = extract_entities(text)

        # Contar entidades extraídas
        total_entities = 0
        for categoria, items in entities_json.get("partes_proceso", {}).items():
            total_entities += len(items)
        for categoria, items in entities_json.get("datos_adicionales", {}).items():
            total_entities += len(items)

        logger.info(f"[{file_id}] Entidades extraídas: {total_entities}")
        entities_count = total_entities

        # Paso 3: Validar extracción
        logger.info(f"[{file_id}] Validando extracción...")
        validation_warnings = validate_extraction(entities_json, text)

        if validation_warnings:
            logger.warning(f"[{file_id}] Se encontraron {len(validation_warnings)} advertencias")
            warnings.extend(validation_warnings)
        else:
            logger.info(f"[{file_id}] Validación completada sin advertencias")

        # Paso 4: Anonimizar texto
        logger.info(f"[{file_id}] Anonimizando texto...")
        anonymized_text, mapeo = anonymize_text(text, entities_json)
        logger.info(f"[{file_id}] Texto anonimizado: {len(anonymized_text)} caracteres, {len(mapeo)} reemplazos")

        # Paso 5: Reconstruir documento
        logger.info(f"[{file_id}] Reconstruyendo documento...")
        output_path = rebuild_document(input_path, anonymized_text)
        logger.info(f"[{file_id}] Documento reconstruido en: {output_path}")

        # Paso 6: Almacenar metadata
        processing_time = (datetime.now() - start_time).total_seconds()

        processed_files[file_id] = {
            "original_name": file.filename,
            "output_path": str(output_path),
            "format": doc_format,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(hours=1),
            "warnings": warnings,
            "entities_count": entities_count,
            "replacements_count": len(mapeo),
            "processing_time": processing_time,
            "original_size": len(text),
            "anonymized_size": len(anonymized_text)
        }

        logger.info(
            f"[{file_id}] Procesamiento completado en {processing_time:.2f}s - "
            f"{entities_count} entidades, {len(mapeo)} reemplazos"
        )

        return {
            "file_id": file_id,
            "original_name": file.filename,
            "format": doc_format,
            "status": "success",
            "message": "Documento procesado correctamente",
            "warnings": warnings,
            "stats": {
                "entities_found": entities_count,
                "replacements_made": len(mapeo),
                "processing_time_seconds": round(processing_time, 2),
                "original_chars": len(text),
                "anonymized_chars": len(anonymized_text)
            }
        }

    except Exception as e:
        logger.error(f"[{file_id}] Error durante procesamiento: {str(e)}", exc_info=True)

        # Limpiar archivo de entrada en caso de error
        if input_path.exists():
            input_path.unlink()
            logger.info(f"[{file_id}] Archivo temporal limpiado tras error")

        raise HTTPException(status_code=500, detail=f"Error al procesar documento: {str(e)}")

    finally:
        # Limpiar archivo de entrada después de procesar
        if input_path.exists():
            input_path.unlink()
            logger.debug(f"[{file_id}] Archivo de entrada limpiado")


@app.get("/download/{file_id}")
async def download_document(file_id: str):
    """
    Endpoint para descargar documento procesado

    Args:
        file_id: ID único del archivo procesado

    Returns:
        Archivo anonimizado (.docx) para descarga

    Note:
        Los archivos expiran después de 1 hora y se limpian automáticamente
    """
    logger.info(f"[{file_id}] Solicitud de descarga recibida")

    # Verificar que el file_id existe
    if file_id not in processed_files:
        logger.warning(f"[{file_id}] Archivo no encontrado en caché")
        raise HTTPException(
            status_code=404,
            detail="Archivo no encontrado o expirado"
        )

    file_info = processed_files[file_id]

    # Verificar expiración
    if datetime.now() > file_info["expires_at"]:
        logger.warning(f"[{file_id}] Archivo expirado")

        # Limpiar archivo expirado
        output_path = Path(file_info["output_path"])
        if output_path.exists():
            output_path.unlink()
            logger.info(f"[{file_id}] Archivo expirado eliminado del disco")

        del processed_files[file_id]

        raise HTTPException(
            status_code=410,
            detail="El archivo ha expirado (tiempo máximo: 1 hora)"
        )

    # Verificar que el archivo existe en disco
    output_path = Path(file_info["output_path"])
    if not output_path.exists():
        logger.error(f"[{file_id}] Archivo no encontrado en disco: {output_path}")
        raise HTTPException(
            status_code=404,
            detail="Archivo no encontrado en el sistema"
        )

    # Generar nombre de descarga
    original_stem = Path(file_info["original_name"]).stem
    download_name = f"anonimizado_{original_stem}.docx"

    logger.info(
        f"[{file_id}] Descarga iniciada - "
        f"Archivo: {download_name}, "
        f"Warnings: {len(file_info.get('warnings', []))}, "
        f"Reemplazos: {file_info.get('replacements_count', 0)}"
    )

    # Retornar archivo
    return FileResponse(
        path=str(output_path),
        filename=download_name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


@app.post("/api/preview")
async def preview_extraction(file: UploadFile = File(...)):
    """
    Preview de extracción de texto (para debugging)

    Args:
        file: Documento judicial (.docx, .doc, .rtf)

    Returns:
        Primeros 500 caracteres del texto extraído
    """
    preview_id = str(uuid.uuid4())[:8]
    logger.info(f"[PREVIEW-{preview_id}] Solicitud de preview: {file.filename}")

    # Validar extensión
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        logger.warning(f"[PREVIEW-{preview_id}] Formato no soportado: {file_ext}")
        raise HTTPException(
            status_code=400,
            detail=f"Formato no soportado. Use: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Validar tamaño
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        logger.warning(f"[PREVIEW-{preview_id}] Archivo demasiado grande")
        raise HTTPException(
            status_code=413,
            detail=f"Archivo demasiado grande. Máximo: {MAX_FILE_SIZE / (1024*1024):.0f}MB"
        )

    # Guardar temporalmente en /tmp
    tmp_path = TMP_DIR / f"preview_{uuid.uuid4()}{file_ext}"
    with open(tmp_path, "wb") as f:
        f.write(content)

    try:
        text, doc_format = process_document(tmp_path)
        logger.info(f"[PREVIEW-{preview_id}] Texto extraído: {len(text)} caracteres, formato: {doc_format}")

        return {
            "format": doc_format,
            "preview": text[:500],
            "total_chars": len(text)
        }
    except Exception as e:
        logger.error(f"[PREVIEW-{preview_id}] Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
            logger.debug(f"[PREVIEW-{preview_id}] Archivo temporal limpiado")


@app.on_event("startup")
async def cleanup_old_files():
    """Limpiar archivos antiguos al iniciar"""
    if TMP_DIR.exists():
        for file in TMP_DIR.glob("*"):
            try:
                file.unlink()
            except Exception:
                pass


def cleanup_expired_files():
    """Limpiar archivos expirados del almacenamiento"""
    expired_ids = []
    for file_id, file_info in processed_files.items():
        if datetime.now() > file_info["expires_at"]:
            # Eliminar archivo del disco
            output_path = Path(file_info["output_path"])
            if output_path.exists():
                output_path.unlink()
            expired_ids.append(file_id)

    # Eliminar metadata de archivos expirados
    for file_id in expired_ids:
        del processed_files[file_id]

    return len(expired_ids)


@app.get("/api/status")
async def get_status():
    """
    Obtener estado del sistema

    Returns:
        Información sobre archivos en procesamiento y espacio usado
    """
    cleanup_expired_files()

    total_files = len(processed_files)
    total_size = 0

    for file_info in processed_files.values():
        output_path = Path(file_info["output_path"])
        if output_path.exists():
            total_size += output_path.stat().st_size

    return {
        "status": "running",
        "active_files": total_files,
        "total_size_mb": round(total_size / (1024*1024), 2),
        "tmp_dir": str(TMP_DIR),
        "max_file_size_mb": MAX_FILE_SIZE / (1024*1024)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
