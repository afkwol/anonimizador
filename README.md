# Anonimizador Judicial v2.0

Sistema web para anonimizar documentos judiciales usando LLM (Large Language Model) para extracción inteligente de entidades.

## Características

- **Extracción Inteligente**: Diferencia entre partes del proceso (a anonimizar) y autores doctrinarios (se preservan)
- **Múltiples Formatos**: Soporta .docx, .doc, .rtf
- **Anonimización Completa**: Nombres, DNI, CUIL, domicilios, teléfonos, emails, cuentas bancarias
- **Variantes**: Detecta y reemplaza todas las variantes de nombres (iniciales, apellidos, pronombres)
- **Validación**: Sistema de advertencias para revisar extracción
- **Privacidad**: Procesamiento local con tu propio LLM
- **Web Interface**: Frontend moderno con drag & drop

## Arquitectura

```
anonimizador/
├── backend/
│   ├── main.py              # FastAPI app con endpoints
│   ├── anonimizador.py      # Lógica de extracción + anonimización
│   ├── document_processor.py # Extracción y reconstrucción de documentos
│   └── requirements.txt     # Dependencias Python
├── frontend/
│   ├── index.html          # UI con Tailwind CSS
│   └── app.js              # Lógica del cliente
├── .env                    # Configuración (crear desde .env.example)
└── README.md
```

## Instalación

### 1. Clonar repositorio

```bash
git clone <repo-url>
cd anonimizador
```

### 2. Instalar dependencias Python

```bash
cd backend
pip install -r requirements.txt
```

**Dependencias especiales según SO:**

- **Linux/Mac** (.doc support): Instalar `antiword`
  ```bash
  # Ubuntu/Debian
  sudo apt-get install antiword

  # macOS
  brew install antiword
  ```

- **Windows** (.doc support): Requiere Microsoft Word instalado + `pywin32`
  ```bash
  pip install pywin32
  ```

### 3. Configurar LLM

Crear archivo `.env` en la raíz del proyecto:

```bash
cp .env.example .env
```

Editar `.env` con tu configuración:

**Opción A: LM Studio (local, gratis)**
```env
OPENAI_API_BASE=http://127.0.0.1:1234/v1
OPENAI_API_KEY=lm-studio
OPENAI_MODEL=granite-3.1-8b-instruct
```

**Opción B: Claude API**
```env
OPENAI_API_BASE=https://api.anthropic.com/v1
OPENAI_API_KEY=sk-ant-tu-key-aqui
OPENAI_MODEL=claude-sonnet-4-20250514
```

**Opción C: OpenRouter**
```env
OPENAI_API_BASE=https://openrouter.ai/api/v1
OPENAI_API_KEY=sk-or-tu-key-aqui
OPENAI_MODEL=anthropic/claude-sonnet-4
```

## Uso

### 1. Iniciar servidor backend

```bash
cd backend
python main.py
```

El servidor estará disponible en: `http://localhost:8000`

### 2. Abrir frontend

Abre en tu navegador: `http://localhost:8000`

O sirve el frontend directamente:
```bash
cd frontend
python -m http.server 8080
# Luego abre: http://localhost:8080
```

### 3. Procesar documento

1. Arrastra o selecciona un archivo (.docx, .doc, .rtf)
2. Click en "Anonimizar Documento"
3. Espera el procesamiento (aparece barra de progreso)
4. Revisa advertencias si las hay
5. Descarga el documento anonimizado

## API Endpoints

### POST /upload

Sube y procesa un documento.

**Request:**
```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@sentencia.docx"
```

**Response:**
```json
{
  "file_id": "uuid-del-archivo",
  "original_name": "sentencia.docx",
  "format": "docx",
  "status": "success",
  "message": "Documento procesado correctamente",
  "warnings": [
    "ADVERTENCIA: 'Juan Pérez' (actor) no tiene variantes definidas"
  ],
  "stats": {
    "entities_found": 15,
    "replacements_made": 42,
    "processing_time_seconds": 3.45,
    "original_chars": 12500,
    "anonymized_chars": 12350
  }
}
```

### GET /download/{file_id}

Descarga documento anonimizado.

**Request:**
```bash
curl -O http://localhost:8000/download/{file_id}
```

**Nota:** Los archivos expiran después de 1 hora.

### POST /api/preview

Vista previa del texto extraído (debugging).

**Request:**
```bash
curl -X POST http://localhost:8000/api/preview \
  -F "file=@documento.docx"
```

**Response:**
```json
{
  "format": "docx",
  "preview": "Primeros 500 caracteres del texto...",
  "total_chars": 12500
}
```

### GET /health

Verifica estado de la API.

```bash
curl http://localhost:8000/health
```

### GET /api/status

Estado del sistema y archivos en caché.

```bash
curl http://localhost:8000/api/status
```

## Pipeline de Anonimización

1. **Extracción de texto**: Convierte .docx/.doc/.rtf a texto plano
2. **Extracción de entidades (LLM)**: Identifica:
   - Partes del proceso (actor, demandado, testigos, peritos, víctimas)
   - Datos adicionales (domicilios, DNI, CUIL, teléfonos, emails, CBU)
   - Variantes (iniciales, apellidos, pronombres)
   - **Preserva**: Doctrinarios, jurisprudencia, magistrados actuantes
3. **Validación**: Verifica que:
   - Doctrinarios no estén en partes
   - Partes tengan variantes
   - Entidades aparezcan en el texto
4. **Anonimización**: Reemplazo programático con placeholders:
   - `[ACTOR]`, `[DEMANDADO]`, `[TESTIGO_1]`
   - `[DOMICILIO]`, `[DOCUMENTO]`, `[EMAIL]`, etc.
5. **Reconstrucción**: Genera nuevo .docx con texto anonimizado

## Estructura del JSON de Entidades

El LLM extrae entidades en este formato:

```json
{
  "partes_proceso": {
    "actor": ["Juan Carlos Pérez"],
    "demandado": ["María González"],
    "testigos": ["Pedro López"],
    "peritos": [],
    "victimas": [],
    "otros_intervinientes": []
  },
  "preservar": {
    "doctrinarios": ["Lorenzetti", "Highton"],
    "jurisprudencia": ["CSJN"],
    "magistrados_actuantes": ["Dr. Juan Martínez"],
    "funcionarios": []
  },
  "variantes": {
    "Juan Carlos Pérez": ["J.C. Pérez", "Pérez", "el actor", "Juan Pérez"],
    "María González": ["M. González", "González", "la demandada"]
  },
  "datos_adicionales": {
    "domicilios": ["Av. Corrientes 1234, CABA"],
    "documentos": ["DNI 12.345.678", "CUIL 20-12345678-9"],
    "telefonos": ["011-4567-8900"],
    "emails": ["juan@example.com"],
    "cuentas_bancarias": ["CBU 0123456789012345678901"]
  }
}
```

## Testing

Ejecutar script de prueba:

```bash
python test.py
```

Esto:
1. Crea un documento de prueba
2. Simula upload al servidor
3. Verifica procesamiento
4. Imprime resultados y warnings

## Configuración de Producción

### CORS

En `backend/main.py`, cambiar:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://tu-dominio.com"],  # Especificar dominio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Límites

Ajustar en `backend/main.py`:
```python
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".docx", ".doc", ".rtf"}
```

### Almacenamiento

Por defecto usa `/tmp/anonimizador`. Para producción, considerar:
- Persistencia en base de datos (file_id -> metadata)
- Almacenamiento en S3/cloud
- Sistema de limpieza automática (cron job)

## Troubleshooting

### Error: "antiword no está instalado"

**Linux:**
```bash
sudo apt-get install antiword
```

**macOS:**
```bash
brew install antiword
```

**Windows:** Instala Microsoft Word o convierte .doc a .docx antes de subir.

### Error: "Error llamando al LLM"

1. Verifica que el servidor LLM esté corriendo (LM Studio, Claude API, etc.)
2. Revisa `OPENAI_API_BASE` en `.env`
3. Verifica que `OPENAI_API_KEY` sea correcta
4. Comprueba logs del servidor: `python main.py`

### Warnings: "no tiene variantes definidas"

Es normal. El LLM a veces no detecta todas las variantes. Puedes:
1. Revisar el documento anonimizado manualmente
2. Ajustar el prompt en `backend/anonimizador.py` (línea 13-51)
3. Usar un modelo más potente (Claude Sonnet 4 > Granite 3.1)

### Archivo demasiado grande

Aumentar `MAX_FILE_SIZE` en `backend/main.py`:
```python
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
```

## Logging

Los logs se imprimen en consola con formato:
```
2025-01-20 10:30:45 - __main__ - INFO - [abc123] Iniciando procesamiento de: sentencia.docx
2025-01-20 10:30:46 - __main__ - INFO - [abc123] Texto extraído: 12500 caracteres, formato: docx
2025-01-20 10:30:50 - __main__ - INFO - [abc123] Entidades extraídas: 15
2025-01-20 10:30:51 - __main__ - WARNING - [abc123] Se encontraron 2 advertencias
2025-01-20 10:30:52 - __main__ - INFO - [abc123] Procesamiento completado en 7.23s - 15 entidades, 42 reemplazos
```

## Contribuir

1. Fork el repositorio
2. Crea branch: `git checkout -b feature/nueva-funcionalidad`
3. Commit: `git commit -m "Agrega nueva funcionalidad"`
4. Push: `git push origin feature/nueva-funcionalidad`
5. Abre Pull Request

## Licencia

MIT License

## Autor

Proyecto Anonimizador Judicial v2.0
