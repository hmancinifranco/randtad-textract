// script.js
document.addEventListener('DOMContentLoaded', function() {
    const pdfInput = document.getElementById('pdfInput');
    const processButton = document.getElementById('processButton');
    const fileNameDiv = document.getElementById('fileName');
    const loadingSpinner = document.getElementById('loadingSpinner');
    const form = document.getElementById('personalInfoForm');

    // API Gateway endpoint - REEMPLAZAR CON TU ENDPOINT
    const API_ENDPOINT = 'TU_API_GATEWAY_ENDPOINT';

    // Manejar la selección de archivo
    pdfInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file && file.type === 'application/pdf') {
            fileNameDiv.textContent = `Selected file: ${file.name}`;
            processButton.disabled = false;
        } else {
            fileNameDiv.textContent = 'Please select a valid PDF file';
            processButton.disabled = true;
        }
    });

    // Manejar el drag and drop
    const dropZone = document.querySelector('.file-upload');
    
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = '#4CAF50';
    });

    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = '#ccc';
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = '#ccc';
        
        const file = e.dataTransfer.files[0];
        if (file && file.type === 'application/pdf') {
            pdfInput.files = e.dataTransfer.files;
            fileNameDiv.textContent = `Selected file: ${file.name}`;
            processButton.disabled = false;
        }
    });

    // Procesar el PDF
    processButton.addEventListener('click', async function() {
        const file = pdfInput.files[0];
        if (!file) return;

        loadingSpinner.classList.remove('hidden');
        processButton.disabled = true;

        try {
            // Convertir PDF a base64
            const base64PDF = await convertToBase64(file);
            
            // Enviar al API Gateway
            const response = await fetch(API_ENDPOINT, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    base64_pdf: base64PDF
                })
            });

            const data = await response.json();
            
            if (response.ok) {
                // Autofill del formulario
                const personalInfo = data.personalInfo;
                document.getElementById('name').value = personalInfo.name || '';
                document.getElementById('email').value = personalInfo.email || '';
                document.getElementById('phone').value = personalInfo.phone || '';
                document.getElementById('address').value = personalInfo.address || '';
                document.getElementById('zipCode').value = personalInfo.zip_code || '';
            } else {
                throw new Error(data.message || 'Error processing PDF');
            }

        } catch (error) {
            alert('Error: ' + error.message);
        } finally {
            loadingSpinner.classList.add('hidden');
            processButton.disabled = false;
        }
    });

    // Función para convertir archivo a base64
    function convertToBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }
});

