import json
import base64
import boto3
import logging
from datetime import datetime

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
        # Log the incoming event for debugging
        log_event('Received event', {
            'event': event
        })

        # Check if body exists and parse it
        if 'body' not in event:
            raise Exception("No body found in event")

        # Parse body content
        try:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        except Exception as e:
            raise Exception(f"Failed to parse body: {str(e)}")

        # Check if file exists in body
        if 'file' not in body:
            raise Exception("No file found in request body")

        # Decode document
        try:
            document = base64.b64decode(body['file'])
        except Exception as e:
            raise Exception(f"Failed to decode base64 file: {str(e)}")
        
        # Extract text using Textract
        try:
            textract_response = textract.detect_document_text(
                Document={'Bytes': document}
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
                "max_new_tokens": 200,
                "top_p": 0.1,
                "top_k": 10,
                "temperature": 0.1
            }
        }
        
        # Call Bedrock without streaming
        try:
            log_event('Calling Bedrock', {
                'prompt_length': len(formatted_text),
                'model_id': LITE_MODEL_ID
            })
            
            response = bedrock.invoke_model(
                modelId=LITE_MODEL_ID,
                body=json.dumps(request_body)
            )
            
            # Process the response
            response_body = json.loads(response.get('body').read())
            full_response = response_body.get('content')[0].get('text', '')
            
            log_event('Bedrock response received', {
                'response_length': len(full_response)
            })
            
        except Exception as e:
            log_event('Bedrock call failed', error=e)
            raise Exception(f'Failed to process with Bedrock: {str(e)}')
        
        # Process response and extract JSON
        try:
            # Buscar el JSON en la respuesta
            json_start = full_response.find('{')
            json_end = full_response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                extracted_info = json.loads(full_response[json_start:json_end])
            else:
                raise Exception("No JSON found in response")
            
            # Validar y completar campos faltantes
            extracted_info = validate_extracted_info(extracted_info)
            
        except Exception as e:
            log_event('Error processing Bedrock response', error=e)
            extracted_info = {
                'fullname': '',
                'phone_number': '',
                'address': '',
                'email': '',
                'zip_code': ''
            }
        
        # Return formatted response
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Authorization,Content-Type,X-Amz-Date,X-Amz-Security-Token,X-Api-Key',
                'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
            },
            'body': json.dumps({
                'personalInfo': extracted_info,
                'rawText': formatted_text[:500]
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
                'Access-Control-Allow-Headers': 'Authorization,Content-Type,X-Amz-Date,X-Amz-Security-Token,X-Api-Key',
                'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
            },
            'body': json.dumps({
                'error': str(e),
                'message': 'Error processing document'
            })
        }