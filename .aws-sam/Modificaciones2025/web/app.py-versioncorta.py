import json
import base64
import boto3
import logging
from datetime import datetime
from pdf2image import convert_from_bytes
from io import BytesIO
from PIL import Image
import uuid
from botocore.exceptions import ClientError

s3 = boto3.client('s3')
sqs = boto3.client('sqs')
S3_BUCKET = 'cv-preprocess-landing'
QUEUE_URL = 'https://sqs.us-west-2.amazonaws.com/533267341537/LambdaCandidatesStep1'

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def log_event(message, data=None, error=None):
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'message': message,
        'data': data,
        'error': str(error) if error else None
    }
    logger.info(json.dumps(log_entry))

def convert_pdf_to_image(pdf_bytes):
    """
    Convierte la primera página del PDF a imagen
    """
    try:
        # Convertir PDF a imagen
        images = convert_from_bytes(pdf_bytes)
        if not images:
            raise Exception("No images extracted from PDF")
        
        # Tomar la primera página
        first_page = images[0]
        
        # Convertir a bytes
        img_byte_arr = BytesIO()
        first_page.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        
        return img_byte_arr
    except Exception as e:
        log_event('Error converting PDF to image', error=e)
        raise Exception(f"Failed to convert PDF to image: {str(e)}")

def clean_and_format_text(textract_response):
    """
    Limpia y formatea el texto extraído de Textract
    """
    text_blocks = []
    for block in textract_response['Blocks']:
        if block['BlockType'] == 'LINE':
            text = block['Text'].strip()
            if text:
                text_blocks.append(text)
    
    return '\n'.join(text_blocks)

def validate_extracted_info(info):
    """
    Valida y asegura que todos los campos requeridos estén presentes
    """
    required_fields = ['fullname', 'phone_number', 'address', 'email', 'zip_code']
    for field in required_fields:
        if field not in info:
            info[field] = ''
    return info

def lambda_handler(event, context):
    textract = boto3.client('textract')
    bedrock = boto3.client('bedrock-runtime', region_name="us-east-1")
    LITE_MODEL_ID = "us.amazon.nova-lite-v1:0"
    
    try:
        # Decode document
        document = base64.b64decode(json.loads(event['body'])['file'])
        
        try:
            # Convertir PDF a imagen
            image_bytes = convert_pdf_to_image(document)
            
            # Extract text using Textract
            textract_response = textract.detect_document_text(
                Document={'Bytes': image_bytes}
            )
            
            formatted_text = clean_and_format_text(textract_response)
            
            log_event('Text extracted and formatted', {
                'text_length': len(formatted_text),
                'text_preview': formatted_text[:200] + '...'
            })
            
        except Exception as e:
            log_event('Textract text detection failed', error=e)
            raise Exception('Failed to detect text with Textract')


        # Prepare Bedrock request
        system_list = [
            {
                "text": """You are a form field extractor. Extract specific information from the provided text. 
                Return only a JSON object with the following keys: fullname, phone_number, address, email, zip_code.
                Format the response exactly as shown below:
                {
                    "fullname": "extracted name",
                    "phone_number": "extracted phone",
                    "address": "extracted address",
                    "email": "extracted email",
                    "zip_code": "extracted zipcode"
                }
                Do not include any additional text or explanation."""
            }
        ]
        
        message_list = [
            {
                "role": "user",
                "content": [{"text": formatted_text}]
            }
        ]
        
        request_body = {
            "schemaVersion": "messages-v1",
            "messages": message_list,
            "system": system_list,
            "inferenceConfig": {
                "max_new_tokens": 5000,
                "top_p": 0.1,
                "top_k": 10,
                "temperature": 0.1
            }
        }


        # Call Bedrock
        try:
            log_event('Calling Bedrock', {
                'prompt_length': len(formatted_text),
                'model_id': LITE_MODEL_ID
            })
            
            response = bedrock.invoke_model(
                modelId=LITE_MODEL_ID,
                body=json.dumps(request_body)
            )
            
            response_body = response.get('body')
            if not response_body:
                raise Exception("Empty response from Bedrock")
                
            response_text = response_body.read().decode('utf-8')
            response_json = json.loads(response_text)
            
            # Extraer el texto de la nueva estructura de respuesta
            full_response = ''
            if ('output' in response_json and 
                'message' in response_json['output'] and 
                'content' in response_json['output']['message'] and 
                len(response_json['output']['message']['content']) > 0):
                
                full_response = response_json['output']['message']['content'][0]['text']
                
                # Limpiar los marcadores de código JSON si están presentes
                full_response = full_response.replace('```json', '').replace('```', '').strip()
                
                log_event('Bedrock response processed', {
                    'response_length': len(full_response),
                    'response_preview': full_response[:200]
                })
            else:
                raise Exception("Invalid response structure from Bedrock")
            
        except Exception as e:
            log_event('Bedrock call failed', {
                'error_type': type(e).__name__,
                'error_message': str(e)
            })
            raise Exception(f'Failed to process with Bedrock: {str(e)}')

        # Process response and extract JSON
        try:
            # El texto ya debería ser JSON, intentar parsearlo directamente
            extracted_info = json.loads(full_response)
            
            # Validar y completar campos faltantes
            extracted_info = validate_extracted_info(extracted_info)
            
            log_event('Successfully extracted information', {
                'extracted_info': extracted_info
            })
            
            # Generar ID único para el documento
            document_id = str(uuid.uuid4())
            
            # Preparar contenido para S3
            s3_key = f"cv_extractions/{datetime.utcnow().strftime('%Y/%m/%d')}/{document_id}.json"
            
            s3_content = {
                    'extracted_info': extracted_info,
                    'raw_text': formatted_text,
                    'metadata': {
                        'document_id': document_id,
                        'created_at': datetime.utcnow().isoformat(),
                        'source': 'web_upload',
                        'extraction_version': '1.0'  # Útil para futuros cambios en el proceso
                    }
             }
            
            try:
                # Subir a S3
                s3.put_object(
                    Bucket=S3_BUCKET,
                    Key=s3_key,
                    Body=json.dumps(s3_content)
                )
                
                # Preparar y enviar mensaje a SQS
                sqs_message = {
                    'document_id': document_id,
                    's3_bucket': S3_BUCKET,
                    's3_key': s3_key,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                sqs.send_message(
                    QueueUrl=QUEUE_URL,
                    MessageBody=json.dumps(sqs_message)
                )
                
                log_event('Document saved to S3 and message sent to SQS', {
                    'document_id': document_id,
                    's3_key': s3_key
                })
                
            except ClientError as e:
                log_event('Error saving to S3 or sending to SQS', error=e)
                # No fallamos la respuesta principal si falla el guardado
            
        except Exception as e:
            log_event('Error processing Bedrock response', {
                'error_type': type(e).__name__,
                'error_message': str(e),
                'full_response': full_response
            })
            extracted_info = {
                'fullname': '',
                'phone_number': '',
                'address': '',
                'email': '',
                'zip_code': ''
            }
        
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'personalInfo': extracted_info,
                'rawText': formatted_text[:500],
                'document_id': document_id if 'document_id' in locals() else None
            })
        }
        
    except Exception as e:
        log_event('Fatal error in handler', {
            'error_type': type(e).__name__,
            'error_message': str(e)
        })
        
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'error': str(e),
                'message': 'Error processing document'
            })
        }