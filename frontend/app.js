/**
 * Frontend JavaScript para Anonimizador Judicial
 */

// Estado de la aplicación
const state = {
    selectedFile: null,
    apiBase: 'http://localhost:8000'
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
    statusText: document.getElementById('statusText')
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
        showError('Formato no válido. Use: .docx, .doc o .rtf');
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

    // Ocultar preview si está abierto
    closePreview();
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
    closePreview();
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
        showError(`Error en vista previa: ${error.message}`);
    }
}

/**
 * Anonimizar documento
 */
async function anonymizeDocument() {
    if (!state.selectedFile) return;

    showProgress('Procesando documento...', 0);

    try {
        // Paso 1: Subir archivo
        updateProgress('Subiendo documento...', 20);
        const formData = new FormData();
        formData.append('file', state.selectedFile);

        // Paso 2: Procesar
        updateProgress('Extrayendo entidades sensibles...', 40);

        const response = await fetch(`${state.apiBase}/api/anonymize`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Error al anonimizar');
        }

        // Paso 3: Descargar resultado
        updateProgress('Generando documento anonimizado...', 80);

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `anonimizado_${state.selectedFile.name}`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        updateProgress('Completado', 100);

        setTimeout(() => {
            hideProgress();
            showSuccess('Documento anonimizado correctamente');
        }, 1000);

    } catch (error) {
        hideProgress();
        showError(`Error al anonimizar: ${error.message}`);
    }
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
    elements.anonymizeBtn.disabled = false;
    elements.previewBtn.disabled = false;
}

/**
 * Mostrar error
 */
function showError(message) {
    alert(`Error: ${message}`);
}

/**
 * Mostrar éxito
 */
function showSuccess(message) {
    alert(`Éxito: ${message}`);
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
