import json
import boto3
import base64
import logging
from typing import Dict, Any
from pdf2image import convert_from_bytes
import io
import traceback
import sys
from PIL import Image

# Configuración de logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class TextractService:
    def __init__(self):
        self.client = boto3.client('textract')
        self.bedrock = boto3.client('bedrock-runtime')

    def analyze_document(self, image_bytes: bytes) -> Dict:
        """
        Analiza el documento usando Amazon Textract
        """
        try:
            response = self.client.analyze_document(
                Document={'Bytes': image_bytes},
                FeatureTypes=['FORMS', 'TABLES', 'LAYOUT']
            )
            return response
        except Exception as e:
            logger.error(f"Error en Textract: {str(e)}")
            raise

    def get_pretty_printed_text(self, blocks: list) -> str:
        """
        Convierte los bloques de Textract en texto formateado
        """
        text = []
        for block in blocks:
            if block['BlockType'] == 'LINE':
                text.append(block['Text'])
        return '\n'.join(text)

def analyze_with_bedrock(self, text: str) -> Dict:
    """
    Analiza el texto usando Amazon Bedrock (Nova Lite) para extraer información
    """
    try:
        # Primero, verifica que tenemos texto para procesar
        if not text:
            raise ValueError("No hay texto para procesar")

        logger.info("Preparando solicitud para Bedrock")
        
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "messages": [
                {
                    "role": "user",
                    "content": f"""Please analyze this CV text and extract the following information in JSON format:
                    - fullname
                    - email
                    - phone
                    - address
                    - zipcode

                    CV Text:
                    {text}

                    Return ONLY a valid JSON object with these fields, nothing else. Use null for missing fields.
                    """
                }
            ],
            "temperature": 0
        }

        logger.info("Invocando Bedrock", extra={"text_length": len(text)})

        response = self.bedrock.invoke_model(
            modelId="anthropic.claude-3-sonnet-20240229-v1:0",  # Actualizando al modelo más reciente
            contentType="application/json",
            accept="application/json",
            body=json.dumps(request_body)
        )

        logger.info("Respuesta recibida de Bedrock")
        
        # Leer la respuesta completa
        response_body = json.loads(response.get('body').read())
        logger.info("Respuesta parseada", extra={"response_type": str(type(response_body))})

        # Extraer el contenido de la respuesta
        content = response_body.get('content', [{}])[0].get('text', '')
        logger.info("Contenido extraído", extra={"content": content[:200]})  # Log primeros 200 caracteres

        # Intentar encontrar y parsear el JSON
        try:
            # Buscar el primer JSON válido en la respuesta
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                json_str = json_match.group()
                extracted_info = json.loads(json_str)
                
                # Verificar que tenemos todos los campos requeridos
                required_fields = {'fullname', 'email', 'phone', 'address', 'zipcode'}
                if not all(field in extracted_info for field in required_fields):
                    missing_fields = required_fields - set(extracted_info.keys())
                    logger.warning(f"Faltan campos en la respuesta: {missing_fields}")
                    # Agregar campos faltantes como null
                    for field in missing_fields:
                        extracted_info[field] = None

                return extracted_info
            else:
                raise ValueError("No se encontró JSON en la respuesta")

        except json.JSONDecodeError as e:
            logger.error(f"Error decodificando JSON: {str(e)}", extra={"content": content})
            raise ValueError(f"Error decodificando JSON: {str(e)}")

    except Exception as e:
        logger.error(f"Error en Bedrock: {str(e)}", extra={
            "error_type": type(e).__name__,
            "error_details": str(e)
        })
        raise

class PDFProcessor:
    @staticmethod
    def pdf_to_image_bytes(pdf_bytes: bytes) -> bytes:
        """
        Convierte la primera página del PDF a una imagen PNG
        """
        try:
            images = convert_from_bytes(
                pdf_bytes,
                fmt='PNG',
                first_page=1,
                last_page=1,
                dpi=300
            )
            
            if not images:
                raise ValueError("No se pudo convertir el PDF a imagen")

            first_page = images[0]
            img_byte_arr = io.BytesIO()
            first_page.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            return img_byte_arr.getvalue()
        except Exception as e:
            logger.error(f"Error convirtiendo PDF a imagen: {str(e)}")
            raise

class CVProcessor:
    def __init__(self):
        self.textract_service = TextractService()
        self.pdf_processor = PDFProcessor()

def process_cv(self, base64_pdf: str) -> Dict:
    """
    Procesa el CV y extrae la información relevante
    """
    try:
        # Decodificar PDF
        pdf_bytes = self._decode_pdf(base64_pdf)
        
        # Convertir PDF a imagen
        logger.info("Convirtiendo PDF a imagen...")
        image_bytes = self.pdf_processor.pdf_to_image_bytes(pdf_bytes)
        
        # Analizar con Textract
        logger.info("Analizando documento con Textract...")
        textract_response = self.textract_service.analyze_document(image_bytes)
        
        # Obtener texto formateado
        formatted_text = self.textract_service.get_pretty_printed_text(
            textract_response['Blocks']
        )
        
        logger.info("Texto extraído de Textract", extra={
            "text_length": len(formatted_text),
            "text_preview": formatted_text[:200]
        })
        
        # Usar Bedrock para extraer la información
        logger.info("Procesando texto con Bedrock...")
        extracted_info = self.textract_service.analyze_with_bedrock(formatted_text)
        
        if not extracted_info:
            raise ValueError("No se pudo extraer información del CV")

        return extracted_info

    except Exception as e:
        logger.error("Error en el procesamiento del CV", extra={
            "error_type": type(e).__name__,
            "error_message": str(e)
        })
        raise
    
    @staticmethod
    def _decode_pdf(base64_pdf: str) -> bytes:
        """
        Decodifica el PDF desde base64
        """
        if ',' in base64_pdf:
            base64_pdf = base64_pdf.split(',')[1]
        return base64.b64decode(base64_pdf)

def create_response(status_code: int, body: Dict) -> Dict:
    """
    Crea una respuesta formateada para API Gateway
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Content-Type': 'application/json'
        },
        'body': json.dumps(body)
    }

def lambda_handler(event: Dict, context: Any) -> Dict:
    """
    Manejador principal de la función Lambda
    """
    try:
        logger.info("Iniciando procesamiento de CV", extra={
            "request_id": context.aws_request_id
        })

        # Validar evento
        if not event or 'body' not in event:
            return create_response(400, {
                'message': "Solicitud inválida: falta el body"
            })

        # Obtener y validar el input
        try:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        except json.JSONDecodeError as e:
            return create_response(400, {
                'message': f"Error decodificando el body: {str(e)}"
            })

        base64_pdf = body.get("base64_pdf")
        if not base64_pdf:
            return create_response(400, {
                'message': "Se requiere el parámetro base64_pdf"
            })

        # Procesar el CV
        cv_processor = CVProcessor()
        try:
            extracted_info = cv_processor.process_cv(base64_pdf)
        except Exception as e:
            logger.error("Error procesando CV", extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "stack_trace": traceback.format_exc()
            })
            return create_response(500, {
                'message': f"Error procesando CV: {str(e)}"
            })

        # Validar resultado
        if not extracted_info:
            return create_response(422, {
                'message': "No se pudo extraer información del CV"
            })

        logger.info("CV procesado exitosamente", extra={
            "request_id": context.aws_request_id,
            "extracted_fields": list(extracted_info.keys())
        })

        return create_response(200, {
            'personalInfo': extracted_info,
            'message': 'CV procesado exitosamente'
        })

    except Exception as e:
        logger.error("Error no manejado", extra={
            "error_type": type(e).__name__,
            "error_message": str(e),
            "stack_trace": traceback.format_exc()
        })
        return create_response(500, {
            'message': f"Error interno del servidor: {str(e)}"
        })