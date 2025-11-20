/**
 * Frontend JavaScript para Anonimizador Judicial
 */

// Estado de la aplicación
const state = {
    selectedFile: null,
    fileId: null,
    apiBase: window.location.origin  // Usa la misma URL desde donde se carga la página
};

// Elementos DOM
const elements = {
    dropZone: document.getElementById('dropZone'),
    fileInput: document.getElementById('fileInput'),
    fileInfo: document.getElementById('fileInfo'),
    fileName: document.getElementById('fileName'),
    fileSize: document.getElementById('fileSize'),
    removeFile: document.getElementById('removeFile'),
    anonymizeBtn: document.getElementById('anonymizeBtn'),
    previewBtn: document.getElementById('previewBtn'),
    progressSection: document.getElementById('progressSection'),
    progressBar: document.getElementById('progressBar'),
    progressText: document.getElementById('progressText'),
    previewSection: document.getElementById('previewSection'),
    previewText: document.getElementById('previewText'),
    totalChars: document.getElementById('totalChars'),
    closePreview: document.getElementById('closePreview'),
    statusDot: document.getElementById('statusDot'),
    statusText: document.getElementById('statusText'),
    resultsSection: document.getElementById('resultsSection'),
    downloadBtn: document.getElementById('downloadBtn'),
    resultFormat: document.getElementById('resultFormat'),
    resultOriginalName: document.getElementById('resultOriginalName'),
    resultFileId: document.getElementById('resultFileId'),
    warningsSection: document.getElementById('warningsSection'),
    warningsList: document.getElementById('warningsList'),
    processAnotherBtn: document.getElementById('processAnotherBtn'),
    errorSection: document.getElementById('errorSection'),
    errorMessage: document.getElementById('errorMessage'),
    errorDetails: document.getElementById('errorDetails'),
    retryBtn: document.getElementById('retryBtn')
};

// Inicialización
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    checkApiHealth();
});

/**
 * Inicializar event listeners
 */
function initializeEventListeners() {
    // Drop zone
    elements.dropZone.addEventListener('click', () => elements.fileInput.click());
    elements.dropZone.addEventListener('dragover', handleDragOver);
    elements.dropZone.addEventListener('dragleave', handleDragLeave);
    elements.dropZone.addEventListener('drop', handleDrop);

    // File input
    elements.fileInput.addEventListener('change', handleFileSelect);

    // Buttons
    elements.removeFile.addEventListener('click', clearFile);
    elements.anonymizeBtn.addEventListener('click', anonymizeDocument);
    elements.previewBtn.addEventListener('click', previewDocument);
    elements.closePreview.addEventListener('click', closePreview);
    elements.downloadBtn.addEventListener('click', downloadDocument);
    elements.processAnotherBtn.addEventListener('click', resetUI);
    elements.retryBtn.addEventListener('click', retryProcess);
}

/**
 * Verificar estado del API
 */
async function checkApiHealth() {
    try {
        const response = await fetch(`${state.apiBase}/health`);
        const data = await response.json();

        if (data.status === 'ok') {
            updateStatus('online', 'Servidor conectado');
        } else {
            updateStatus('error', 'Error en servidor');
        }
    } catch (error) {
        updateStatus('offline', 'Servidor no disponible');
        console.error('Error verificando salud del API:', error);
    }
}

/**
 * Actualizar indicador de estado
 */
function updateStatus(status, message) {
    const colors = {
        online: 'bg-green-500',
        offline: 'bg-red-500',
        error: 'bg-yellow-500'
    };

    elements.statusDot.className = `w-3 h-3 rounded-full ${colors[status] || 'bg-gray-400'}`;
    elements.statusText.textContent = message;
}

/**
 * Manejar drag over
 */
function handleDragOver(e) {
    e.preventDefault();
    elements.dropZone.classList.add('border-indigo-500', 'bg-indigo-50');
}

/**
 * Manejar drag leave
 */
function handleDragLeave(e) {
    e.preventDefault();
    elements.dropZone.classList.remove('border-indigo-500', 'bg-indigo-50');
}

/**
 * Manejar drop de archivo
 */
function handleDrop(e) {
    e.preventDefault();
    elements.dropZone.classList.remove('border-indigo-500', 'bg-indigo-50');

    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFile(files[0]);
    }
}

/**
 * Manejar selección de archivo
 */
function handleFileSelect(e) {
    const files = e.target.files;
    if (files.length > 0) {
        handleFile(files[0]);
    }
}

/**
 * Procesar archivo seleccionado
 */
function handleFile(file) {
    // Validar extensión
    const validExtensions = ['.docx', '.doc', '.rtf'];
    const fileName = file.name.toLowerCase();
    const isValid = validExtensions.some(ext => fileName.endsWith(ext));

    if (!isValid) {
        showErrorUI('Formato no válido', 'Use archivos .docx, .doc o .rtf');
        return;
    }

    // Validar tamaño (10MB)
    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
        showErrorUI(
            'Archivo demasiado grande',
            `El archivo excede el límite de 10MB. Tamaño: ${formatFileSize(file.size)}`
        );
        return;
    }

    // Guardar archivo
    state.selectedFile = file;

    // Mostrar información
    elements.fileName.textContent = file.name;
    elements.fileSize.textContent = formatFileSize(file.size);
    elements.fileInfo.classList.remove('hidden');

    // Habilitar botones
    elements.anonymizeBtn.disabled = false;
    elements.previewBtn.disabled = false;

    // Ocultar secciones anteriores
    hideAllSections();
}

/**
 * Limpiar archivo seleccionado
 */
function clearFile() {
    state.selectedFile = null;
    elements.fileInput.value = '';
    elements.fileInfo.classList.add('hidden');
    elements.anonymizeBtn.disabled = true;
    elements.previewBtn.disabled = true;
    hideAllSections();
}

/**
 * Vista previa del documento
 */
async function previewDocument() {
    if (!state.selectedFile) return;

    showProgress('Extrayendo texto del documento...', 30);

    try {
        const formData = new FormData();
        formData.append('file', state.selectedFile);

        const response = await fetch(`${state.apiBase}/api/preview`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Error al procesar');
        }

        const data = await response.json();

        // Mostrar preview
        elements.previewText.textContent = data.preview + '\n\n[... texto truncado ...]';
        elements.totalChars.textContent = data.total_chars.toLocaleString();
        elements.previewSection.classList.remove('hidden');

        hideProgress();
    } catch (error) {
        hideProgress();
        showErrorUI('Error en vista previa', error.message);
    }
}

/**
 * Anonimizar documento
 */
async function anonymizeDocument() {
    if (!state.selectedFile) return;

    // Ocultar secciones anteriores
    hideAllSections();

    showProgress('Subiendo documento...', 10);

    try {
        // Paso 1: Subir y procesar
        const formData = new FormData();
        formData.append('file', state.selectedFile);

        updateProgress('Extrayendo texto del documento...', 25);
        updateProgress('Identificando entidades con LLM...', 50);

        const response = await fetch(`${state.apiBase}/upload`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Error al procesar documento');
        }

        const data = await response.json();

        // Guardar file_id
        state.fileId = data.file_id;

        updateProgress('Documento procesado exitosamente', 100);

        // Mostrar resultados
        setTimeout(() => {
            hideProgress();
            showResults(data);
        }, 500);

    } catch (error) {
        hideProgress();
        showErrorUI('Error al anonimizar documento', error.message);
    }
}

/**
 * Descargar documento anonimizado
 */
async function downloadDocument() {
    if (!state.fileId) {
        showErrorUI('Error', 'No hay documento disponible para descargar');
        return;
    }

    try {
        const response = await fetch(`${state.apiBase}/download/${state.fileId}`);

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Error al descargar');
        }

        // Descargar archivo
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `anonimizado_${state.selectedFile.name.replace(/\.[^.]+$/, '')}.txt`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

    } catch (error) {
        showErrorUI('Error al descargar', error.message);
    }
}

/**
 * Mostrar resultados
 */
function showResults(data) {
    // Llenar datos
    elements.resultFormat.textContent = data.format.toUpperCase();
    elements.resultOriginalName.textContent = data.original_name;
    elements.resultFileId.textContent = data.file_id.substring(0, 8) + '...';

    // Mostrar warnings si existen (simulado por ahora)
    const warnings = data.warnings || [];
    if (warnings.length > 0) {
        elements.warningsList.innerHTML = '';
        warnings.forEach(warning => {
            const li = document.createElement('li');
            li.textContent = warning;
            elements.warningsList.appendChild(li);
        });
        elements.warningsSection.classList.remove('hidden');
    } else {
        elements.warningsSection.classList.add('hidden');
    }

    // Mostrar sección de resultados
    elements.resultsSection.classList.remove('hidden');
}

/**
 * Mostrar error en UI
 */
function showErrorUI(title, details) {
    elements.errorMessage.textContent = title;
    elements.errorDetails.textContent = details;
    elements.errorSection.classList.remove('hidden');
}

/**
 * Reintentar proceso
 */
function retryProcess() {
    hideAllSections();
    if (state.selectedFile) {
        anonymizeDocument();
    }
}

/**
 * Resetear UI para procesar otro documento
 */
function resetUI() {
    hideAllSections();
    clearFile();
    state.fileId = null;
}

/**
 * Ocultar todas las secciones
 */
function hideAllSections() {
    elements.previewSection.classList.add('hidden');
    elements.resultsSection.classList.add('hidden');
    elements.errorSection.classList.add('hidden');
    elements.progressSection.classList.add('hidden');
}

/**
 * Cerrar vista previa
 */
function closePreview() {
    elements.previewSection.classList.add('hidden');
}

/**
 * Mostrar progreso
 */
function showProgress(message, percent) {
    elements.progressSection.classList.remove('hidden');
    elements.progressText.textContent = message;
    elements.progressBar.style.width = `${percent}%`;
    elements.anonymizeBtn.disabled = true;
    elements.previewBtn.disabled = true;
}

/**
 * Actualizar progreso
 */
function updateProgress(message, percent) {
    elements.progressText.textContent = message;
    elements.progressBar.style.width = `${percent}%`;
}

/**
 * Ocultar progreso
 */
function hideProgress() {
    elements.progressSection.classList.add('hidden');
    elements.progressBar.style.width = '0%';
    if (state.selectedFile) {
        elements.anonymizeBtn.disabled = false;
        elements.previewBtn.disabled = false;
    }
}

/**
 * Formatear tamaño de archivo
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}
