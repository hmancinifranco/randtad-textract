// script.js

// Configuración
const API_ENDPOINT = 'https://zr0u3ubrzl.execute-api.us-west-2.amazonaws.com/prod/process-cv'; // Reemplazar con tu URL de API Gateway

// Elementos del DOM
const elements = {
    pdfInput: document.getElementById('pdfInput'),
    fileName: document.getElementById('fileName'),
    processButton: document.getElementById('processButton'),
    loadingSpinner: document.getElementById('loadingSpinner'),
    form: document.getElementById('personalInfoForm'),
};

// Estado
let selectedFile = null;

// Event Listeners
document.addEventListener('DOMContentLoaded', initializeApp);
elements.pdfInput.addEventListener('change', handleFileSelect);
elements.processButton.addEventListener('click', processPDF);

// Drag and Drop
const dropZone = elements.pdfInput.parentElement;
dropZone.addEventListener('dragover', handleDragOver);
dropZone.addEventListener('drop', handleDrop);

function initializeApp() {
    validateFileInput();
}

function handleFileSelect(event) {
    const file = event.target.files[0];
    updateFileSelection(file);
}

function handleDragOver(event) {
    event.preventDefault();
    event.stopPropagation();
    dropZone.classList.add('dragover');
}

function handleDrop(event) {
    event.preventDefault();
    event.stopPropagation();
    dropZone.classList.remove('dragover');
    
    const file = event.dataTransfer.files[0];
    if (file && file.type === 'application/pdf') {
        elements.pdfInput.files = event.dataTransfer.files;
        updateFileSelection(file);
    } else {
        showError('Please upload a PDF file');
    }
}

function updateFileSelection(file) {
    const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB

    if (!file) {
        showError('No file selected');
        resetForm();
        return;
    }

    if (file.type !== 'application/pdf') {
        showError('Please select a valid PDF file');
        resetForm();
        return;
    }

    if (file.size > MAX_FILE_SIZE) {
        showError('File size exceeds 5MB limit');
        resetForm();
        return;
    }

    selectedFile = file;
    elements.fileName.textContent = file.name;
    elements.processButton.disabled = false;
}

async function processPDF() {
    if (!selectedFile) {
        showError('Please select a PDF file first');
        return;
    }

    try {
        showLoading(true);
        
        // Convertir PDF a base64
        const base64Data = await convertToBase64(selectedFile);
        // Extraer solo la parte de datos base64 (eliminar el prefijo data:application/pdf;base64,)
        const base64Clean = base64Data.split(',')[1];
        
        // Llamar a la API
        const response = await fetch(API_ENDPOINT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                file: base64Clean // Cambiar base64_pdf por file
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(`Error: ${errorData.message || response.statusText}`);
        }

        const data = await response.json();
        
        // Verificar que data.personalInfo existe
        if (!data.personalInfo) {
            throw new Error('Invalid response format from server');
        }
        
        // Actualizar el formulario con la información extraída
        updateForm(data.personalInfo);
        showSuccess('CV processed successfully!');

    } catch (error) {
        console.error('Error processing PDF:', error);
        showError(`Error processing PDF: ${error.message}`);
    } finally {
        showLoading(false);
    }
}

function updateForm(personalInfo) {
    // Mapear los campos del formulario con la información extraída
    const fieldMappings = {
        'name': personalInfo.fullname || '',
        'phone': personalInfo.phone_number || '',
        'address': personalInfo.address || '',
        'email': personalInfo.email || '',
        'zipCode': personalInfo.zip_code || ''
    };

    // Actualizar cada campo del formulario
    Object.entries(fieldMappings).forEach(([fieldId, value]) => {
        const input = document.getElementById(fieldId);
        if (input) {
            input.value = value;
            // Efecto visual para mostrar que el campo se ha actualizado
            input.classList.add('updated');
            setTimeout(() => input.classList.remove('updated'), 1000);
        }
    });
}

function convertToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = error => reject(error);
        reader.readAsDataURL(file);
    });
}

function showLoading(show) {
    elements.loadingSpinner.classList.toggle('hidden', !show);
    elements.processButton.disabled = show;
}

function showError(message) {
    // Crear o usar un elemento para mostrar errores
    const errorDiv = document.getElementById('errorMessage') || createErrorElement();
    errorDiv.textContent = message;
    errorDiv.classList.remove('hidden');
    
    // Ocultar el mensaje después de 5 segundos
    setTimeout(() => {
        errorDiv.classList.add('hidden');
    }, 5000);
}

function createErrorElement() {
    const errorDiv = document.createElement('div');
    errorDiv.id = 'errorMessage';
    errorDiv.className = 'error-message';
    document.body.appendChild(errorDiv);
    return errorDiv;
}

function showSuccess(message) {
    const successDiv = document.getElementById('successMessage') || createSuccessElement();
    successDiv.textContent = message;
    successDiv.classList.remove('hidden');
    
    setTimeout(() => {
        successDiv.classList.add('hidden');
    }, 3000);
}

function createSuccessElement() {
    const successDiv = document.createElement('div');
    successDiv.id = 'successMessage';
    successDiv.className = 'success-message';
    document.body.appendChild(successDiv);
    return successDiv;
}

function showSuccessMessage() {
    const successMessage = document.getElementById('successMessage');
    successMessage.classList.remove('hidden');
    
    // Automatically hide the message after 3 seconds
    setTimeout(() => {
        successMessage.classList.add('hidden');
    }, 3000);
}

// Call this function when the PDF is successfully uploaded
document.getElementById('pdfInput').addEventListener('change', function(event) {
    if (event.target.files.length > 0) {
        showSuccessMessage();
        // Enable process button
        document.getElementById('processButton').disabled = false;
    }
});


function resetForm() {
    selectedFile = null;
    elements.fileName.textContent = '';
    elements.processButton.disabled = true;
    elements.form.reset();
}