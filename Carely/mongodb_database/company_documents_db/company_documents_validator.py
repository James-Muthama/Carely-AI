# CompanyDocuments Collection Validator
# This validator defines the schema for storing PDF document metadata in the RAG system
# Each document record tracks the processing status, file information, and metadata

company_documents_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["company_id", "file_path", "file_name", "uploaded_at", "processing_status"],
        "properties": {
            "company_id": {
                "bsonType": "objectId",
                "description": "Enter the unique company/customer identifier as a string"
            },
            "file_path": {
                "bsonType": "string",
                "description": "Enter the full path to the uploaded PDF file"
            },
            "file_name": {
                "bsonType": "string",
                "description": "Enter the original name of the uploaded file"
            },
            "total_pages": {
                "bsonType": ["int", "null"],
                "description": "Enter the total number of pages in the PDF document as integer"
            },
            "total_chunks": {
                "bsonType": ["int", "null"],
                "description": "Enter the total number of text chunks created from the document"
            },
            "chunk_size": {
                "bsonType": ["int", "null"],
                "description": "Enter the size of each text chunk used for processing"
            },
            "chunk_overlap": {
                "bsonType": ["int", "null"],
                "description": "Enter the overlap between consecutive chunks in characters"
            },
            "uploaded_at": {
                "bsonType": "date",
                "description": "Enter the timestamp when the document was uploaded"
            },
            "processing_status": {
                "bsonType": "string",
                "enum": ["completed", "failed", "processing"],
                "description": "Enter the document processing status (completed/failed/processing)"
            },
            "error_message": {
                "bsonType": ["string", "null"],
                "description": "Enter the error message if document processing failed"
            },
            "failed_at": {
                "bsonType": ["date", "null"],
                "description": "Enter the timestamp when document processing failed"
            }
        }
    }
}