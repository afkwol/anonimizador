"""
FastAPI Backend para Anonimizador Judicial
"""
import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from document_processor import process_document
from anonimizador import anonymize_text

# Cargar variables de entorno
load_dotenv()

app = FastAPI(
    title="Anonimizador Judicial",
    description="API para anonimizar documentos judiciales",
    version="2.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


@app.post("/api/anonymize")
async def anonymize_document(file: UploadFile = File(...)):
    """
    Endpoint principal para anonimizar documentos

    Args:
        file: Documento judicial (.docx, .doc, .rtf)

    Returns:
        Documento anonimizado para descarga
    """
    # Validar extensión
    allowed_extensions = {".docx", ".doc", ".rtf"}
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no soportado. Use: {', '.join(allowed_extensions)}"
        )

    # Crear archivo temporal
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_input:
        content = await file.read()
        tmp_input.write(content)
        tmp_input_path = Path(tmp_input.name)

    try:
        # 1. Extraer texto del documento
        text, doc_format = process_document(tmp_input_path)

        # 2. Anonimizar con LLM
        anonymized_text = await anonymize_text(text)

        # 3. Crear documento de salida
        output_path = tmp_input_path.parent / f"anonimizado_{file.filename}"

        # Por ahora, guardamos como .txt (luego podemos reconstruir el formato)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(anonymized_text)

        # Retornar documento anonimizado
        return FileResponse(
            path=str(output_path),
            filename=f"anonimizado_{Path(file.filename).stem}.txt",
            media_type="text/plain"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Limpiar archivos temporales
        if tmp_input_path.exists():
            tmp_input_path.unlink()


@app.post("/api/preview")
async def preview_extraction(file: UploadFile = File(...)):
    """
    Preview de extracción de texto (para debugging)

    Returns:
        Primeros 500 caracteres del texto extraído
    """
    file_ext = Path(file.filename).suffix.lower()

    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
