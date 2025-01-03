import json
import boto3
import pymongo
import logging
from datetime import datetime
from botocore.exceptions import ClientError
from pymongo.errors import PyMongoError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configuración
MONGO_URI = "tu_uri_de_documentdb"
DB_NAME = "candidates_db"
COLLECTION_NAME = "cv_extractions"

def get_mongo_client():
    return pymongo.MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=5000,  # 5 segundos de timeout
        connectTimeoutMS=5000,
        retryWrites=False  # Importante para DocumentDB
    )

def log_event(message, data=None, error=None):
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'message': message,
        'data': data,
        'error': str(error) if error else None
    }
    logger.info(json.dumps(log_entry))

def validate_message(message_body):
    """Valida que el mensaje tenga todos los campos necesarios"""
    required_fields = ['document_id', 's3_bucket', 's3_key', 'timestamp']
    for field in required_fields:
        if field not in message_body:
            raise ValueError(f"Missing required field: {field}")

def lambda_handler(event, context):
    s3 = boto3.client('s3')
    client = None
    
    try:
        for record in event['Records']:
            try:
                message_body = json.loads(record['body'])
                validate_message(message_body)
                
                log_event('Processing message', {
                    'document_id': message_body['document_id'],
                    's3_key': message_body['s3_key']
                })

                # Obtener datos de S3
                try:
                    s3_response = s3.get_object(
                        Bucket=message_body['s3_bucket'],
                        Key=message_body['s3_key']
                    )
                    cv_data = json.loads(s3_response['Body'].read().decode('utf-8'))
                except ClientError as e:
                    log_event('Error retrieving from S3', error=e)
                    raise

                # Validar datos de CV
                if 'extracted_info' not in cv_data or 'raw_text' not in cv_data:
                    raise ValueError("Invalid CV data structure")

                # Conectar a DocumentDB
                client = get_mongo_client()
                db = client[DB_NAME]
                collection = db[COLLECTION_NAME]

                # Preparar documento
                document = {
                    '_id': message_body['document_id'],
                    'extracted_info': cv_data['extracted_info'],
                    'raw_text': cv_data['raw_text'],
                    'created_at': cv_data['timestamp'],
                    'updated_at': datetime.utcnow().isoformat(),
                    's3_reference': {
                        'bucket': message_body['s3_bucket'],
                        'key': message_body['s3_key']
                    },
                    'processing_metadata': {
                        'processed_at': datetime.utcnow().isoformat(),
                        'sqs_message_id': record.get('messageId'),
                        'aws_request_id': context.aws_request_id
                    }
                }

                # Insertar en DocumentDB
                try:
                    collection.insert_one(document)
                    log_event('Document inserted successfully', {
                        'document_id': message_body['document_id']
                    })
                except PyMongoError as e:
                    log_event('Error inserting document', error=e)
                    raise

            except Exception as e:
                log_event('Error processing record', {
                    'record_id': record.get('messageId')
                }, error=e)
                # No reintentamos el mensaje individual, pero continuamos con los siguientes
                continue

        return {
            'statusCode': 200,
            'body': json.dumps('Successfully processed all messages')
        }

    except Exception as e:
        log_event('Fatal error in handler', error=e)
        raise

    finally:
        # Cerrar conexión MongoDB si está abierta
        if client:
            try:
                client.close()
            except Exception as e:
                log_event('Error closing MongoDB connection', error=e)