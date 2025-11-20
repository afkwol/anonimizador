"""
Lógica de anonimización con LLM
Estrategia: Extracción de entidades + Reemplazo programático
"""
import os
import re
from typing import List, Dict, Any
import asyncio

from openai import AsyncOpenAI


# Inicializar cliente OpenAI (compatible con LM Studio y otros)
client = AsyncOpenAI(
    base_url=os.getenv("OPENAI_API_BASE", "http://127.0.0.1:1234/v1"),
    api_key=os.getenv("OPENAI_API_KEY", "lm-studio")
)

# Prompts del sistema
EXTRACTION_PROMPT = """Eres un asistente especializado en análisis de documentos judiciales argentinos.

Tu tarea es identificar y extraer TODAS las entidades sensibles que deben ser anonimizadas.

**IMPORTANTE: Diferencia entre:**
1. **PARTES DEL PROCESO** (deben anonimizarse):
   - Demandantes, demandados, querellantes
   - Testigos, peritos
   - Letrados de las partes
   - Cualquier persona involucrada en el proceso judicial

2. **AUTORES DOCTRINARIOS** (NO se anonimiza):
   - Juristas citados en doctrina
   - Autores de libros, papers, jurisprudencia
   - Jueces de fallos citados como precedente

**ENTIDADES A EXTRAER:**
- nombres_personas: Lista de nombres completos de partes del proceso
- domicilios: Direcciones físicas
- documentos: DNI, CUIL, CUIT, pasaportes
- telefonos: Números de teléfono
- emails: Correos electrónicos
- cuentas_bancarias: CBU, alias, números de tarjeta

**FORMATO DE SALIDA (JSON):**
{
  "nombres_personas": ["Juan Pérez", "María González"],
  "domicilios": ["Av. Corrientes 1234", "Calle Falsa 123"],
  "documentos": ["30.123.456", "27-12345678-9"],
  "telefonos": ["011-4567-8900"],
  "emails": ["juan@ejemplo.com"],
  "cuentas_bancarias": ["0123456789012345678901"]
}

**NO incluyas:**
- Jueces del tribunal que dicta sentencia (son parte del fallo oficial)
- Autores citados en la doctrina
- Referencias bibliográficas
- Números de expediente, fechas, montos

Devuelve SOLO el JSON, sin explicaciones."""

REPLACEMENT_PROMPT = """Eres un asistente que anonimiza documentos judiciales.

Reemplaza las siguientes entidades sensibles con placeholders:

ENTIDADES A REEMPLAZAR:
{entities}

REGLAS:
1. Reemplaza cada ocurrencia con el placeholder correspondiente
2. Mantén TODO el resto del texto idéntico
3. No modifiques números de expediente, fechas, montos
4. No modifiques nombres de autores doctrinarios citados
5. Conserva formato, puntuación y saltos de línea

PLACEHOLDERS:
- Nombres de personas → [NOMBRE APELLIDO]
- Domicilios → [DOMICILIO]
- Documentos → [DOCUMENTO]
- Teléfonos → [TELEFONO]
- Emails → [EMAIL]
- Cuentas bancarias → [CUENTA BANCARIA]

Devuelve el texto completo anonimizado."""


async def extract_entities(text: str, chunk_size: int = 8000) -> Dict[str, List[str]]:
    """
    Extrae entidades sensibles usando LLM

    Args:
        text: Texto del documento
        chunk_size: Tamaño máximo de chunk para el LLM

    Returns:
        Diccionario con entidades extraídas
    """
    # Si el texto es muy largo, dividir en chunks
    chunks = split_text(text, chunk_size)

    all_entities = {
        "nombres_personas": set(),
        "domicilios": set(),
        "documentos": set(),
        "telefonos": set(),
        "emails": set(),
        "cuentas_bancarias": set()
    }

    # Procesar cada chunk
    for chunk in chunks:
        try:
            response = await client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
                messages=[
                    {"role": "system", "content": EXTRACTION_PROMPT},
                    {"role": "user", "content": chunk}
                ],
                temperature=0.0,
                max_tokens=1000
            )

            # Parsear respuesta JSON
            content = response.choices[0].message.content
            import json
            entities = json.loads(content)

            # Agregar a conjunto global
            for key in all_entities:
                if key in entities:
                    all_entities[key].update(entities[key])

        except Exception as e:
            print(f"Error extrayendo entidades: {e}")
            continue

    # Convertir sets a listas
    return {k: list(v) for k, v in all_entities.items()}


def replace_entities(text: str, entities: Dict[str, List[str]]) -> str:
    """
    Reemplaza entidades sensibles con placeholders

    Args:
        text: Texto original
        entities: Entidades a reemplazar

    Returns:
        Texto anonimizado
    """
    result = text

    # Mapeo de categorías a placeholders
    placeholders = {
        "nombres_personas": "[NOMBRE APELLIDO]",
        "domicilios": "[DOMICILIO]",
        "documentos": "[DOCUMENTO]",
        "telefonos": "[TELEFONO]",
        "emails": "[EMAIL]",
        "cuentas_bancarias": "[CUENTA BANCARIA]"
    }

    # Reemplazar cada entidad
    for category, entity_list in entities.items():
        placeholder = placeholders.get(category, "[REDACTADO]")

        for entity in entity_list:
            if not entity or not entity.strip():
                continue

            # Escapar caracteres especiales para regex
            pattern = re.escape(entity)
            result = re.sub(pattern, placeholder, result, flags=re.IGNORECASE)

    return result


async def anonymize_text(text: str) -> str:
    """
    Anonimiza texto completo usando estrategia híbrida

    Estrategia:
    1. LLM extrae entidades sensibles
    2. Reemplazo programático con placeholders

    Args:
        text: Texto a anonimizar

    Returns:
        Texto anonimizado
    """
    # Paso 1: Extraer entidades con LLM
    entities = await extract_entities(text)

    # Paso 2: Reemplazo programático
    anonymized = replace_entities(text, entities)

    return anonymized


def split_text(text: str, chunk_size: int = 8000) -> List[str]:
    """
    Divide texto en chunks respetando párrafos

    Args:
        text: Texto a dividir
        chunk_size: Tamaño máximo de cada chunk

    Returns:
        Lista de chunks
    """
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = []
    current_size = 0

    for para in paragraphs:
        para_size = len(para)

        if current_size + para_size > chunk_size and current_chunk:
            # Guardar chunk actual
            chunks.append("\n\n".join(current_chunk))
            current_chunk = [para]
            current_size = para_size
        else:
            current_chunk.append(para)
            current_size += para_size

    # Agregar último chunk
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks
