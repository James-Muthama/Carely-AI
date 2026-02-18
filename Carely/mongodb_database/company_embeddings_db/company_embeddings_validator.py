# CompanyEmbeddings Collection Validator
# This validator defines the schema for storing vector embeddings and text chunks
# Each record represents a processed text chunk with its embedding and metadata

company_embeddings_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["company_id", "document_id", "chunk_id", "created_at"],
        "properties": {
            "company_id": {
                "bsonType": "objectId",
                "description": "Enter the unique company/customer identifier as a string"
            },
            "document_id": {
                "bsonType": "string",
                "description": "Enter the reference ID to the source document"
            },
            "chunk_id": {
                "bsonType": "string",
                "description": "Enter the unique identifier for this text chunk"
            },
            "chunk_text": {
                "bsonType": ["string", "null"],
                "description": "Enter the actual text content of the chunk"
            },
            "embedding_vector": {
                "bsonType": ["binData", "array", "null"],
                "description": "Enter the vector embedding as binary data or array of numbers"
            },
            "page_number": {
                "bsonType": ["int", "null"],
                "description": "Enter the page number where this chunk originated"
            },
            "chunk_index": {
                "bsonType": ["int", "null"],
                "description": "Enter the sequential index of this chunk within the document"
            },
            "metadata": {
                "bsonType": ["object", "null"],
                "description": "Enter additional metadata for the chunk as an object",
                "properties": {
                    "source": {
                        "bsonType": ["string", "null"],
                        "description": "Enter the source file information"
                    },
                    "page": {
                        "bsonType": ["int", "null"],
                        "description": "Enter the page number from metadata"
                    }
                }
            },
            "created_at": {
                "bsonType": "date",
                "description": "Enter the timestamp when the embedding was created"
            }
        }
    }
}