# Anonimizador Judicial v2.0

Web application para anonimizar documentos judiciales (.docx, .doc, .rtf) usando LLM local.

## Stack Técnico

- **Backend**: FastAPI (Python 3.9+)
- **Frontend**: HTML + JavaScript + Tailwind CSS
- **Procesamiento**: python-docx, striprtf
- **LLM**: OpenAI-compatible API (LM Studio, Ollama, etc.)

## Estructura del Proyecto

```
anonimizador-judicial/
├── backend/
│   ├── main.py                  # FastAPI application
│   ├── anonimizador.py          # Lógica de anonimización con LLM
│   ├── document_processor.py    # Procesamiento de .docx, .doc, .rtf
│   └── requirements.txt         # Dependencias Python
├── frontend/
│   ├── index.html              # Interfaz web
│   └── app.js                  # Lógica frontend
└── .env                        # Configuración (no incluido en git)
```

## Instalación

### 1. Clonar repositorio

```bash
git clone <repo-url>
cd anonimizador
```

### 2. Configurar entorno virtual

```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
cd backend
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env` con tu configuración:

```env
OPENAI_API_BASE=http://127.0.0.1:1234/v1
OPENAI_API_KEY=lm-studio
OPENAI_MODEL=granite-3.1-8b-instruct
```

### 5. Iniciar LM Studio

1. Abrir LM Studio
2. Cargar modelo (recomendado: granite-3.1-8b-instruct o superior)
3. Iniciar servidor local (Start Server)
4. Verificar que esté corriendo en `http://127.0.0.1:1234`

## Uso

### Iniciar servidor

```bash
cd backend
python main.py
```

O con uvicorn:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Acceder a la aplicación

Abrir navegador en: `http://localhost:8000`

## Funcionalidad

### Flujo de trabajo

1. **Usuario sube documento** judicial (.docx, .doc, .rtf)
2. **Backend extrae texto** usando procesadores específicos
3. **LLM identifica entidades sensibles**:
   - Diferencia entre partes del proceso (a anonimizar) y autores doctrinarios (preservar)
   - Extrae: nombres, DNI, domicilios, teléfonos, emails, cuentas bancarias
4. **Reemplazo programático** con placeholders
5. **Reconstrucción** del documento anonimizado
6. **Usuario descarga** resultado

### Estrategia de anonimización

**Dos pasos:**

1. **Extracción (LLM)**: Identifica entidades sensibles usando prompt especializado
2. **Reemplazo (programático)**: Sustituye entidades por placeholders

**Ventajas:**
- Más preciso que reemplazo directo con LLM
- Preserva estructura del documento
- Diferencia partes del proceso vs autores doctrinarios

### Placeholders utilizados

- `[NOMBRE APELLIDO]` - Partes del proceso, testigos, letrados
- `[DOMICILIO]` - Direcciones físicas
- `[DOCUMENTO]` - DNI, CUIL, CUIT, pasaportes
- `[TELEFONO]` - Números telefónicos
- `[EMAIL]` - Correos electrónicos
- `[CUENTA BANCARIA]` - CBU, alias, tarjetas

### Qué se preserva

- Números de expediente
- Fechas
- Montos y valores numéricos
- Nombres de jueces del tribunal
- Autores doctrinarios citados
- Referencias bibliográficas
- Estructura del documento

## API Endpoints

### `GET /health`
Verificar estado del servidor

**Response:**
```json
{
  "status": "ok",
  "llm_endpoint": "http://127.0.0.1:1234/v1"
}
```

### `POST /api/anonymize`
Anonimizar documento

**Request:**
- Form data con archivo (`file`)

**Response:**
- Archivo anonimizado (.txt)

### `POST /api/preview`
Vista previa de extracción

**Request:**
- Form data con archivo (`file`)

**Response:**
```json
{
  "format": "docx",
  "preview": "Primeros 500 caracteres...",
  "total_chars": 15234
}
```

## Formatos Soportados

### .docx
- Extracción nativa con `python-docx`
- Soportado en todos los sistemas operativos

### .doc (formato antiguo)
- **Windows**: Usa COM automation (requiere Word instalado)
- **Linux/Mac**: Requiere `antiword`
  ```bash
  # Ubuntu/Debian
  sudo apt-get install antiword

  # macOS
  brew install antiword
  ```

### .rtf
- Extracción con `striprtf`
- Soportado en todos los sistemas operativos

## Desarrollo

### Estructura de código

**Backend:**
- `main.py`: Endpoints FastAPI, manejo de archivos
- `document_processor.py`: Extracción de texto por formato
- `anonimizador.py`: Lógica LLM (extracción + reemplazo)

**Frontend:**
- `index.html`: UI con Tailwind CSS
- `app.js`: Manejo de eventos, llamadas API, drag & drop

### Mejoras futuras

- [ ] Reconstruir formato original (.docx output)
- [ ] Batch processing (múltiples archivos)
- [ ] Revisión manual de entidades antes de anonimizar
- [ ] Exportar reporte de cambios
- [ ] Soporte para PDF
- [ ] Tests unitarios
- [ ] Docker deployment

## Requisitos del Sistema

- Python 3.9+
- LM Studio (o API compatible con OpenAI)
- Navegador moderno (Chrome, Firefox, Edge)

**Para .doc (opcional):**
- Windows: Microsoft Word
- Linux/Mac: antiword

## Troubleshooting

### Error: "Servidor no disponible"
- Verificar que LM Studio esté corriendo
- Verificar URL en `.env` (default: `http://127.0.0.1:1234/v1`)

### Error al procesar .doc
- **Windows**: Instalar Microsoft Word
- **Linux/Mac**: Instalar antiword
- Alternativa: Convertir a .docx antes de subir

### Error: "Modelo no encontrado"
- Verificar que el modelo en `.env` esté cargado en LM Studio
- Verificar nombre exacto del modelo

## Licencia

MIT

## Contacto

Para reportar problemas o sugerencias, abrir un issue en el repositorio.
