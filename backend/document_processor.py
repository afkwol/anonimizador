"""
Procesamiento de documentos judiciales
Soporta: .docx, .doc, .rtf
"""
import platform
from pathlib import Path
from typing import Tuple

from docx import Document
from striprtf.striprtf import rtf_to_text


def extract_text_from_docx(file_path: Path) -> str:
    """
    Extrae texto de archivos .docx

    Args:
        file_path: Ruta al archivo .docx

    Returns:
        Texto extraído
    """
    doc = Document(str(file_path))
    paragraphs = [para.text for para in doc.paragraphs]
    return "\n".join(paragraphs)


def extract_text_from_doc(file_path: Path) -> str:
    """
    Extrae texto de archivos .doc (formato antiguo de Word)

    Args:
        file_path: Ruta al archivo .doc

    Returns:
        Texto extraído

    Note:
        En Windows usa win32com, en otros sistemas intenta antiword
    """
    if platform.system() == "Windows":
        return _extract_doc_windows(file_path)
    else:
        return _extract_doc_antiword(file_path)


def _extract_doc_windows(file_path: Path) -> str:
    """Extrae .doc usando COM en Windows"""
    try:
        import win32com.client
    except ImportError:
        raise ImportError(
            "Para procesar archivos .doc en Windows necesitas instalar pywin32: "
            "pip install pywin32"
        )

    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False

    try:
        doc = word.Documents.Open(str(file_path.absolute()))
        text = doc.Content.Text
        doc.Close()
        return text
    finally:
        word.Quit()


def _extract_doc_antiword(file_path: Path) -> str:
    """Extrae .doc usando antiword en Linux/Mac"""
    import subprocess

    try:
        result = subprocess.run(
            ["antiword", str(file_path)],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except FileNotFoundError:
        raise RuntimeError(
            "Para procesar archivos .doc en Linux/Mac necesitas instalar antiword: "
            "sudo apt-get install antiword (Debian/Ubuntu) o brew install antiword (Mac)"
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error al procesar .doc: {e.stderr}")


def extract_text_from_rtf(file_path: Path) -> str:
    """
    Extrae texto de archivos .rtf

    Args:
        file_path: Ruta al archivo .rtf

    Returns:
        Texto extraído
    """
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        rtf_content = f.read()

    text = rtf_to_text(rtf_content)
    return text


def process_document(file_path: Path) -> Tuple[str, str]:
    """
    Procesa un documento y extrae su texto

    Args:
        file_path: Ruta al documento

    Returns:
        Tupla (texto_extraido, formato_documento)

    Raises:
        ValueError: Si el formato no es soportado
    """
    ext = file_path.suffix.lower()

    extractors = {
        ".docx": ("docx", extract_text_from_docx),
        ".doc": ("doc", extract_text_from_doc),
        ".rtf": ("rtf", extract_text_from_rtf),
    }

    if ext not in extractors:
        raise ValueError(
            f"Formato no soportado: {ext}. "
            f"Formatos válidos: {', '.join(extractors.keys())}"
        )

    doc_format, extractor = extractors[ext]
    text = extractor(file_path)

    if not text or not text.strip():
        raise ValueError("El documento está vacío o no se pudo extraer texto")

    return text, doc_format
