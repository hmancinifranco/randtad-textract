// script.js

// Configuración
const CONFIG = {
    API_ENDPOINT: 'https://zr0u3ubrzl.execute-api.us-west-2.amazonaws.com/prod/process-cv',
    MAX_FILE_SIZE: 5 * 1024 * 1024, // 5MB
    TIMEOUT_DURATION: 30000, // 30 segundos
    MESSAGE_DURATION: {
        ERROR: 5000,
        SUCCESS: 3000
    }
};

// Elementos del DOM
const elements = {
    pdfInput: document.getElementById('pdfInput'),
    fileName: document.getElementById('fileName'),
    processButton: document.getElementById('processButton'),
    loadingSpinner: document.getElementById('loadingSpinner'),
    form: document.getElementById('personalInfoForm'),
    dropZone: document.getElementById('pdfInput').parentElement
};

// Estado
let selectedFile = null;

// Inicialización
document.addEventListener('DOMContentLoaded', initializeApp);

// Event Listeners
function setupEventListeners() {
    elements.pdfInput.addEventListener('change', handleFileSelect);
    elements.processButton.addEventListener('click', processPDF);
    elements.dropZone.addEventListener('dragover', handleDragOver);
    elements.dropZone.addEventListener('drop', handleDrop);
    elements.dropZone.addEventListener('dragleave', handleDragLeave);
}

function initializeApp() {
    if (validateDOMElements()) {
        setupEventListeners();
        elements.processButton.disabled = true;
    }
}

function validateDOMElements() {
    const requiredElements = ['pdfInput', 'fileName', 'processButton', 'loadingSpinner', 'form'];
    const missingElements = requiredElements.filter(elementId => !elements[elementId]);
    
    if (missingElements.length > 0) {
        console.error('Missing required DOM elements:', missingElements);
        return false;
    }
    return true;
}

// Manejadores de archivos
function handleFileSelect(event) {
    updateFileSelection(event.target.files[0]);
}

function handleDragOver(event) {
    event.preventDefault();
    event.stopPropagation();
    elements.dropZone.classList.add('dragover');
}

function handleDragLeave(event) {
    event.preventDefault();
    event.stopPropagation();
    elements.dropZone.classList.remove('dragover');
}

function handleDrop(event) {
    event.preventDefault();
    event.stopPropagation();
    elements.dropZone.classList.remove('dragover');
    
    const file = event.dataTransfer.files[0];
    if (file?.type === 'application/pdf') {
        elements.pdfInput.files = event.dataTransfer.files;
        updateFileSelection(file);
    } else {
        showError('Por favor, sube un archivo PDF');
    }
}

function updateFileSelection(file) {
    if (!validateFile(file)) {
        resetForm();
        return;
    }

    selectedFile = file;
    elements.fileName.textContent = file.name;
    elements.processButton.disabled = false;
}

function validateFile(file) {
    if (!file) {
        showError('No se ha seleccionado ningún archivo');
        return false;
    }

    if (file.type !== 'application/pdf') {
        showError('Por favor, selecciona un archivo PDF válido');
        return false;
    }

    if (file.size > CONFIG.MAX_FILE_SIZE) {
        showError('El archivo excede el límite de 5MB');
        return false;
    }

    return true;
}

// Procesamiento del PDF
async function processPDF() {
    if (!selectedFile) {
        showError('Por favor, selecciona un archivo PDF primero');
        return;
    }

    try {
        showLoading(true);
        const base64Data = await convertToBase64(selectedFile);
        const base64Clean = base64Data.split(',')[1];
        
        const response = await fetchWithTimeout(
            CONFIG.API_ENDPOINT,
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file: base64Clean })
            },
            CONFIG.TIMEOUT_DURATION
        );

        const data = await response.json();
        
        if (!data.personalInfo) {
            throw new Error('Formato de respuesta inválido del servidor');
        }
        
        updateForm(data.personalInfo);
        showSuccess('CV procesado exitosamente');

    } catch (error) {
        handleProcessError(error);
    } finally {
        showLoading(false);
    }
}

async function fetchWithTimeout(resource, options, timeout) {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);
    
    try {
        const response = await fetch(resource, {
            ...options,
            signal: controller.signal
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return response;
    } finally {
        clearTimeout(id);
    }
}

// Actualización del formulario
function updateForm(personalInfo) {
    const fieldMappings = {
        'firstName': personalInfo.firstname || '',
        'lastName': personalInfo.lastname || '',
        'email': personalInfo.email || '',
        'documentType': personalInfo.document_type || '',
        'birthCountry': personalInfo.birth_country || '',
        'birthDate': personalInfo.birth_date || '',
        'gender': personalInfo.gender || '',
        'phone': personalInfo.phone_number || '',
        'residenceCountry': personalInfo.residence_country || '',
        'province': personalInfo.province || '',
        'city': personalInfo.city || '',
        'zipCode': personalInfo.zip_code || '',
        'address': personalInfo.address || ''
    };

    Object.entries(fieldMappings).forEach(([fieldId, value]) => {
        const input = document.getElementById(fieldId);
        if (input) {
            input.value = value;
            highlightUpdatedField(input);
        }
    });
}

// Utilidades
function convertToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

function showLoading(show) {
    elements.loadingSpinner.classList.toggle('hidden', !show);
    elements.processButton.disabled = show;
    elements.processButton.textContent = show ? 'Procesando...' : 'Procesar CV';
}

function handleProcessError(error) {
    const errorMessage = error.name === 'AbortError' 
        ? 'La solicitud ha excedido el tiempo límite. Por favor, intenta de nuevo.'
        : `Error al procesar el PDF: ${error.message}`;
    
    console.error('Error processing PDF:', error);
    showError(errorMessage);
}

function showMessage(message, type) {
    const messageDiv = document.getElementById(`${type}Message`) || 
                      createMessageElement(type);
    messageDiv.textContent = message;
    messageDiv.classList.remove('hidden');
    
    setTimeout(() => {
        messageDiv.classList.add('hidden');
    }, CONFIG.MESSAGE_DURATION[type.toUpperCase()]);
}

function showError(message) {
    showMessage(message, 'error');
}

function showSuccess(message) {
    showMessage(message, 'success');
}

function createMessageElement(type) {
    const div = document.createElement('div');
    div.id = `${type}Message`;
    div.className = `${type}-message`;
    document.body.appendChild(div);
    return div;
}

function highlightUpdatedField(input) {
    input.classList.add('updated');
    setTimeout(() => input.classList.remove('updated'), 1000);
}

function resetForm() {
    selectedFile = null;
    elements.fileName.textContent = '';
    elements.processButton.disabled = true;
    elements.form.reset();
    elements.pdfInput.value = '';
}