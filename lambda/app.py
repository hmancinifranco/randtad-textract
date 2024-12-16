import json
import boto3
import base64
import re

textract_client = boto3.client('textract')

def extract_personal_info(blocks):
    """
    Extrae información personal específica del CV usando patrones comunes
    """
    personal_info = {
        'name': None,
        'email': None,
        'phone': None,
        'address': None,
        'zip_code': None
    }
    
    # Patrones para matching
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    phone_pattern = r'\b(?:\+?1[-.]?)?\s*(?:\([0-9]{3}\)|[0-9]{3})[-.]?[0-9]{3}[-.]?[0-9]{4}\b'
    zip_pattern = r'\b\d{5}(?:-\d{4})?\b'

    text_blocks = [block['Text'] for block in blocks if block.get('BlockType') == 'LINE']
    
    for text in text_blocks:
        # Buscar email
        if not personal_info['email']:
            email_match = re.search(email_pattern, text)
            if email_match:
                personal_info['email'] = email_match.group()

        # Buscar teléfono
        if not personal_info['phone']:
            phone_match = re.search(phone_pattern, text)
            if phone_match:
                personal_info['phone'] = phone_match.group()

        # Buscar código postal
        if not personal_info['zip_code']:
            zip_match = re.search(zip_pattern, text)
            if zip_match:
                personal_info['zip_code'] = zip_match.group()

        # Buscar nombre (asumiendo que está en las primeras líneas)
        if not personal_info['name'] and len(text.split()) <= 4:
            # Evitar líneas que contienen email o teléfono
            if not re.search(email_pattern, text) and not re.search(phone_pattern, text):
                personal_info['name'] = text.strip()

        # Buscar dirección (líneas que contienen el código postal)
        if not personal_info['address'] and personal_info['zip_code'] and personal_info['zip_code'] in text:
            personal_info['address'] = text.strip()

    return personal_info

def validate_pdf_size(decoded_bytes):
    """
    Valida el tamaño del PDF
    """
    MAX_SIZE = 5242880  # 5MB en bytes
    if len(decoded_bytes) > MAX_SIZE:
        raise ValueError("PDF size exceeds maximum allowed size of 5MB")

def lambda_handler(event, context):
    try:
        # Parse the input JSON from the API Gateway
        body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        base64_pdf = body.get("base64_pdf")
        
        if not base64_pdf:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': "The body param base64_pdf is required."}),
            }

        # Remover el prefijo de data URL si existe
        if ',' in base64_pdf:
            base64_pdf = base64_pdf.split(',')[1]

        # Decodificar el PDF
        decoded_bytes = base64.b64decode(base64_pdf)
        
        # Validar tamaño del PDF
        validate_pdf_size(decoded_bytes)

        # Llamar a Textract para analizar el documento
        textract_response = textract_client.analyze_document(
            Document={
                'Bytes': decoded_bytes
            },
            FeatureTypes=['FORMS', 'TABLES']  # Incluir TABLES para mejor extracción
        )

        # Procesar la respuesta de Textract
        personal_info = extract_personal_info(textract_response['Blocks'])

        # Preparar la respuesta
        response = {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'personalInfo': personal_info,
                'message': 'PDF processed successfully'
            }),
        }

    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
        response = {
            'statusCode': 400,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'message': f"Error processing PDF: {str(e)}"
            }),
        }

    return response