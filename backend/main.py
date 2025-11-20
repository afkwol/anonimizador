"""
FastAPI Backend para Anonimizador Judicial
"""
import os
import uuid
import tempfile
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime, timedelta

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from document_processor import process_document
from anonimizador import anonymize_text_full

# Cargar variables de entorno
load_dotenv()

# Configuración
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".docx", ".doc", ".rtf"}
TMP_DIR = Path("/tmp/anonimizador")
TMP_DIR.mkdir(exist_ok=True)

# Almacenamiento temporal de archivos procesados (file_id -> path)
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

    Args:
        file: Documento judicial (.docx, .doc, .rtf)

    Returns:
        JSON con file_id para descargar resultado
    """
    # Validar extensión
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no soportado. Use: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Validar tamaño
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Archivo demasiado grande. Máximo: {MAX_FILE_SIZE / (1024*1024):.0f}MB"
        )

    # Generar ID único
    file_id = str(uuid.uuid4())

    # Guardar archivo temporal en /tmp
    input_path = TMP_DIR / f"{file_id}_input{file_ext}"
    with open(input_path, "wb") as f:
        f.write(content)

    try:
        # 1. Extraer texto del documento
        text, doc_format = process_document(input_path)

        # 2. Anonimizar con LLM (extracción + reemplazo)
        anonymized_text = await anonymize_text_full(text)

        # 3. Guardar documento anonimizado
        output_path = TMP_DIR / f"{file_id}_output.txt"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(anonymized_text)

        # 4. Almacenar metadata
        processed_files[file_id] = {
            "original_name": file.filename,
            "output_path": str(output_path),
            "format": doc_format,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(hours=1)
        }

        return {
            "file_id": file_id,
            "original_name": file.filename,
            "format": doc_format,
            "status": "success",
            "message": "Documento procesado correctamente"
        }

    except Exception as e:
        # Limpiar archivo de entrada en caso de error
        if input_path.exists():
            input_path.unlink()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Limpiar archivo de entrada después de procesar
        if input_path.exists():
            input_path.unlink()


@app.get("/download/{file_id}")
async def download_document(file_id: str):
    """
    Endpoint para descargar documento procesado

    Args:
        file_id: ID único del archivo procesado

    Returns:
        Archivo anonimizado para descarga
    """
    # Verificar que el file_id existe
    if file_id not in processed_files:
        raise HTTPException(
            status_code=404,
            detail="Archivo no encontrado o expirado"
        )

    file_info = processed_files[file_id]

    # Verificar expiración
    if datetime.now() > file_info["expires_at"]:
        # Limpiar archivo expirado
        output_path = Path(file_info["output_path"])
        if output_path.exists():
            output_path.unlink()
        del processed_files[file_id]
        raise HTTPException(
            status_code=410,
            detail="El archivo ha expirado"
        )

    # Verificar que el archivo existe en disco
    output_path = Path(file_info["output_path"])
    if not output_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Archivo no encontrado en el sistema"
        )

    # Generar nombre de descarga
    original_stem = Path(file_info["original_name"]).stem
    download_name = f"anonimizado_{original_stem}.txt"

    # Retornar archivo
    return FileResponse(
        path=str(output_path),
        filename=download_name,
        media_type="text/plain"
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
    # Validar extensión
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no soportado. Use: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Validar tamaño
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
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
        return {
            "format": doc_format,
            "preview": text[:500],
            "total_chars": len(text)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


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
