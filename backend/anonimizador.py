"""
Lógica de anonimización con LLM
Estrategia: Extracción de entidades + Reemplazo programático
"""
import os
import re
import json
from typing import Dict, List, Any, Tuple
import requests


# Prompt de extracción mejorado
PROMPT_EXTRACCION_MEJORADO = """
Analiza esta sentencia judicial y extrae TODAS las personas mencionadas, clasificándolas:

Devuelve JSON con esta estructura EXACTA:
{{
  "partes_proceso": {{
    "actor": ["nombre completo con todas las variantes"],
    "demandado": ["nombre completo con variantes"],
    "testigos": ["lista"],
    "peritos": ["lista"],
    "victimas": ["lista"],
    "otros_intervinientes": ["lista"]
  }},
  "preservar": {{
    "doctrinarios": ["lista de autores citados"],
    "jurisprudencia": ["jueces de fallos citados"],
    "magistrados_actuantes": ["juez/jueces de este caso"],
    "funcionarios": ["en contexto oficial"]
  }},
  "variantes": {{
    "Juan Carlos Pérez": ["J.C. Pérez", "Pérez", "Juan Pérez", "el actor"]
  }},
  "datos_adicionales": {{
    "domicilios": ["direcciones completas"],
    "documentos": ["DNI, CUIL, CUIT"],
    "telefonos": ["números de teléfono"],
    "emails": ["correos electrónicos"],
    "cuentas_bancarias": ["CBU, alias, tarjetas"]
  }}
}}

CRÍTICO: En "variantes" incluye TODAS las formas en que aparece cada persona
(iniciales, apellido solo, pronombres como "la actora", "el demandado").

TEXTO:
{texto}

RESPONDE SOLO CON JSON VÁLIDO.
"""

# Lista de doctrinarios conocidos (para validación)
DOCTRINARIOS_CONOCIDOS = [
    "lorenzetti", "highton", "maqueda", "rosatti", "rosenkrantz",
    "llambías", "borda", "salvat", "spota", "belluscio",
    "fallos", "csjn", "scba", "cámara nacional"
]


def call_llm(prompt: str, text: str) -> Dict[str, Any]:
    """
    Llama al LLM con el prompt y texto proporcionado

    Args:
        prompt: System prompt
        text: Texto a procesar

    Returns:
        Respuesta parseada del LLM (JSON)

    Raises:
        Exception: Si falla la llamada o el parseo
    """
    endpoint = os.getenv("OPENAI_API_BASE", "http://127.0.0.1:1234/v1")
    api_key = os.getenv("OPENAI_API_KEY", "lm-studio")
    model = os.getenv("OPENAI_MODEL", "granite-3.1-8b-instruct")

    # Preparar request
    url = f"{endpoint.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text}
        ],
        "temperature": 0.0,
        "max_tokens": 2000
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        # Intentar parsear JSON
        # Limpiar markdown si viene con ```json
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        return json.loads(content)

    except requests.RequestException as e:
        raise Exception(f"Error llamando al LLM: {e}")
    except json.JSONDecodeError as e:
        raise Exception(f"Error parseando respuesta del LLM: {e}\nContenido: {content}")
    except (KeyError, IndexError) as e:
        raise Exception(f"Formato de respuesta inválido: {e}")


def extract_entities(text: str) -> Dict[str, Any]:
    """
    Extrae entidades del texto usando LLM con clasificación mejorada

    Args:
        text: Texto del documento judicial

    Returns:
        JSON con entidades clasificadas
    """
    # Si el texto es muy largo, dividir en chunks
    if len(text) > 10000:
        chunks = split_text_smart(text, 8000)
        all_entities = merge_entities_from_chunks(chunks)
        return all_entities

    # Formatear prompt con el texto
    prompt = PROMPT_EXTRACCION_MEJORADO.format(texto=text)

    # Llamar al LLM
    entities_json = call_llm(prompt, text)

    return entities_json


def validate_extraction(entities_json: Dict[str, Any], text: str) -> List[str]:
    """
    Valida la extracción de entidades y genera warnings

    Args:
        entities_json: Entidades extraídas
        text: Texto original

    Returns:
        Lista de warnings
    """
    warnings = []

    # 1. Verificar que doctrinarios conocidos no estén en partes
    partes_todas = []
    for categoria, nombres in entities_json.get("partes_proceso", {}).items():
        partes_todas.extend([n.lower() for n in nombres])

    for doctrinario in DOCTRINARIOS_CONOCIDOS:
        for parte in partes_todas:
            if doctrinario in parte:
                warnings.append(
                    f"ADVERTENCIA: '{parte}' podría ser un doctrinario, "
                    f"no una parte del proceso"
                )

    # 2. Verificar que haya variantes para las partes principales
    variantes = entities_json.get("variantes", {})
    for categoria in ["actor", "demandado"]:
        nombres = entities_json.get("partes_proceso", {}).get(categoria, [])
        for nombre in nombres:
            if nombre not in variantes or len(variantes[nombre]) < 2:
                warnings.append(
                    f"ADVERTENCIA: '{nombre}' ({categoria}) no tiene variantes definidas. "
                    f"Podría aparecer de otras formas en el texto."
                )

    # 3. Verificar que las entidades aparezcan en el texto
    for categoria, nombres in entities_json.get("partes_proceso", {}).items():
        for nombre in nombres:
            if nombre.lower() not in text.lower():
                warnings.append(
                    f"ADVERTENCIA: '{nombre}' ({categoria}) no aparece en el texto"
                )

    return warnings


def anonymize_text(text: str, entities_json: Dict[str, Any]) -> Tuple[str, Dict[str, str]]:
    """
    Anonimiza texto con control inteligente de variantes

    Args:
        text: Texto original
        entities_json: Entidades extraídas por el LLM

    Returns:
        Tupla (texto_anonimizado, mapeo_de_cambios)
    """
    mapeo = {}
    contador = {"testigos": 0, "peritos": 0, "victimas": 0, "otros_intervinientes": 0}

    # 1. Crear mapeo de todas las variantes de partes del proceso
    for tipo, personas in entities_json.get("partes_proceso", {}).items():
        for persona in personas:
            # Determinar tag según tipo
            if tipo in ["actor", "demandado"]:
                tag = f"[{tipo.upper()}]"
            else:
                contador[tipo] += 1
                tag = f"[{tipo.upper()}_{contador[tipo]}]"

            # Mapear persona y todas sus variantes
            variantes = entities_json.get("variantes", {}).get(persona, [persona])
            for variante in variantes:
                if variante not in mapeo:  # Evitar sobreescribir
                    mapeo[variante] = tag

    # 2. Agregar datos adicionales al mapeo
    datos_adicionales = entities_json.get("datos_adicionales", {})
    placeholders_adicionales = {
        "domicilios": "[DOMICILIO]",
        "documentos": "[DOCUMENTO]",
        "telefonos": "[TELEFONO]",
        "emails": "[EMAIL]",
        "cuentas_bancarias": "[CUENTA BANCARIA]"
    }

    for categoria, items in datos_adicionales.items():
        placeholder = placeholders_adicionales.get(categoria, "[REDACTADO]")
        for item in items:
            if item not in mapeo:
                mapeo[item] = placeholder

    # 3. Reemplazar en el texto (ordenar por longitud para evitar reemplazos parciales)
    texto_anonimizado = text

    for original in sorted(mapeo.keys(), key=len, reverse=True):
        # Usar word boundaries para evitar reemplazos parciales
        patron = r'\b' + re.escape(original) + r'\b'
        texto_anonimizado = re.sub(
            patron,
            mapeo[original],
            texto_anonimizado,
            flags=re.IGNORECASE
        )

    return texto_anonimizado, mapeo


def split_text_smart(text: str, chunk_size: int = 8000) -> List[str]:
    """
    Divide texto inteligentemente respetando párrafos

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
            chunks.append("\n\n".join(current_chunk))
            current_chunk = [para]
            current_size = para_size
        else:
            current_chunk.append(para)
            current_size += para_size

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks


def merge_entities_from_chunks(chunks: List[str]) -> Dict[str, Any]:
    """
    Extrae entidades de múltiples chunks y las fusiona

    Args:
        chunks: Lista de fragmentos de texto

    Returns:
        Entidades fusionadas
    """
    merged = {
        "partes_proceso": {
            "actor": set(),
            "demandado": set(),
            "testigos": set(),
            "peritos": set(),
            "victimas": set(),
            "otros_intervinientes": set()
        },
        "preservar": {
            "doctrinarios": set(),
            "jurisprudencia": set(),
            "magistrados_actuantes": set(),
            "funcionarios": set()
        },
        "variantes": {},
        "datos_adicionales": {
            "domicilios": set(),
            "documentos": set(),
            "telefonos": set(),
            "emails": set(),
            "cuentas_bancarias": set()
        }
    }

    for chunk in chunks:
        try:
            entities = extract_entities(chunk)

            # Fusionar partes_proceso
            for categoria in merged["partes_proceso"]:
                if categoria in entities.get("partes_proceso", {}):
                    merged["partes_proceso"][categoria].update(
                        entities["partes_proceso"][categoria]
                    )

            # Fusionar preservar
            for categoria in merged["preservar"]:
                if categoria in entities.get("preservar", {}):
                    merged["preservar"][categoria].update(
                        entities["preservar"][categoria]
                    )

            # Fusionar variantes
            for nombre, vars in entities.get("variantes", {}).items():
                if nombre not in merged["variantes"]:
                    merged["variantes"][nombre] = set()
                merged["variantes"][nombre].update(vars)

            # Fusionar datos adicionales
            for categoria in merged["datos_adicionales"]:
                if categoria in entities.get("datos_adicionales", {}):
                    merged["datos_adicionales"][categoria].update(
                        entities["datos_adicionales"][categoria]
                    )

        except Exception as e:
            print(f"Error procesando chunk: {e}")
            continue

    # Convertir sets a listas
    result = {
        "partes_proceso": {k: list(v) for k, v in merged["partes_proceso"].items()},
        "preservar": {k: list(v) for k, v in merged["preservar"].items()},
        "variantes": {k: list(v) for k, v in merged["variantes"].items()},
        "datos_adicionales": {k: list(v) for k, v in merged["datos_adicionales"].items()}
    }

    return result


# Función principal (async para compatibilidad con FastAPI)
async def anonymize_text_full(text: str) -> str:
    """
    Pipeline completo de anonimización

    Args:
        text: Texto a anonimizar

    Returns:
        Texto anonimizado
    """
    # 1. Extraer entidades
    entities = extract_entities(text)

    # 2. Validar extracción
    warnings = validate_extraction(entities, text)
    if warnings:
        print("ADVERTENCIAS DE VALIDACIÓN:")
        for warning in warnings:
            print(f"  - {warning}")

    # 3. Anonimizar
    anonymized, mapeo = anonymize_text(text, entities)

    # Log del mapeo (para debugging)
    print(f"\nReemplazos realizados: {len(mapeo)} entidades")

    return anonymized
