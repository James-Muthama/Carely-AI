import os
from flask import Blueprint, request, flash, redirect, url_for, session, render_template, jsonify, current_app
from werkzeug.utils import secure_filename
from Carely.app.utils import login_required, allowed_file
from Carely.app.services import get_or_create_rag_system

# Create the Blueprint
rag_bp = Blueprint('rag', __name__)

@rag_bp.route('/customer_agent')
@login_required
def customer_agent():
    return render_template('customer_agent.html')


@rag_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_file():
    """
    Handle PDF file upload and process it through the persistent RAG system.
    UPDATED: Keeps the file on disk so the Business Agent can analyze it later.
    """
    if request.method == 'POST':
        try:
            if 'file' not in request.files:
                flash('No file selected', 'error')
                return redirect(request.url)

            file = request.files['file']

            if file.filename == '':
                flash('No file selected', 'error')
                return redirect(request.url)

            if not allowed_file(file.filename):
                flash('Only PDF files are allowed', 'error')
                return redirect(request.url)

            filename = secure_filename(file.filename)

            # Create unique filename
            import uuid
            unique_filename = f"{uuid.uuid4()}_{filename}"
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)

            # Save the file to disk
            file.save(filepath)

            # Initialize RAG
            rag_system = get_or_create_rag_system()

            if rag_system is None:
                flash('Error initializing RAG system', 'error')
                # Only delete if INIT fails
                if os.path.exists(filepath):
                    os.remove(filepath)
                return redirect(request.url)

            print(f"Processing PDF: {filepath}")

            # Process with RAG
            # Note: We keep the file path in the DB so Business Agent can find it
            success = rag_system.upload_file(filepath)

            if success:
                session['rag_system_ready'] = True
                session['uploaded_filename'] = filename

                flash(f'Document {filename} processed successfully!', 'success')

                # --- CHANGE IS HERE ---
                # We REMOVED the os.remove(filepath) code.
                # The file now stays in the 'uploads' folder.
                # ----------------------

                return redirect(url_for('rag.chat_interface'))

            else:
                flash('Error processing the PDF file.', 'error')
                # Only delete if PROCESSING fails
                if os.path.exists(filepath):
                    os.remove(filepath)
                return redirect(request.url)

        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'error')
            print(f"Upload error: {str(e)}")
            return redirect(request.url)

    # GET request handling...
    rag_system = get_or_create_rag_system()
    existing_docs = []
    if rag_system:
        existing_docs = rag_system.get_company_documents()
        session['rag_system_ready'] = len(existing_docs) > 0

    return render_template('upload_pdf.html',
                           rag_ready=session.get('rag_system_ready', False),
                           uploaded_file=session.get('uploaded_filename'),
                           existing_documents=existing_docs)

@rag_bp.route('/ask_question', methods=['POST'])
@login_required
def ask_question():
    """
    Handle questions sent to the persistent RAG system
    """
    try:
        # Get RAG system for this company
        rag_system = get_or_create_rag_system()

        if rag_system is None:
            return jsonify({
                'error': 'RAG system not available',
                'status': 'system_error'
            }), 500

        # Check if company has any processed documents
        company_docs = rag_system.get_company_documents()
        if not company_docs:
            return jsonify({
                'error': 'Please upload a PDF document first',
                'status': 'no_document'
            }), 400

        # Get question from request
        data = request.get_json()
        if not data or 'question' not in data:
            return jsonify({
                'error': 'No question provided',
                'status': 'invalid_request'
            }), 400

        question = data['question'].strip()
        if not question:
            return jsonify({
                'error': 'Question cannot be empty',
                'status': 'invalid_request'
            }), 400

        # Get answer from persistent RAG system
        answer = rag_system.ask_question(question)

        # Optionally get relevant documents for transparency
        relevant_docs = rag_system.get_relevant_documents(question, k=3)

        return jsonify({
            'answer': answer,
            'question': question,
            'relevant_documents': [
                {
                    'content': doc['content'][:200] + '...' if len(doc['content']) > 200 else doc['content'],
                    'score': doc['relevance_score']
                }
                for doc in relevant_docs
            ],
            'status': 'success'
        })

    except Exception as e:
        print(f"Question processing error: {str(e)}")
        return jsonify({
            'error': f'Error processing question: {str(e)}',
            'status': 'processing_error'
        }), 500

@rag_bp.route('/chat_interface')
@login_required
def chat_interface():
    """
    Display the chat interface for asking questions with persistent data
    """
    rag_system = get_or_create_rag_system()

    if rag_system is None:
        flash('Error loading RAG system', 'error')
        return redirect(url_for('rag.upload_file'))

    # Get company's processed documents
    company_docs = rag_system.get_company_documents()

    if not company_docs:
        flash('Please upload a PDF document first', 'warning')
        return redirect(url_for('rag.upload_file'))

    return render_template('chat.html',
                           uploaded_file=session.get('uploaded_filename'),
                           existing_documents=company_docs)

@rag_bp.route('/clear_conversation', methods=['POST'])
@login_required
def clear_conversation():
    """
    Clear the conversation history (persistent)
    """
    try:
        rag_system = get_or_create_rag_system()
        if rag_system:
            rag_system.clear_conversation_history()
            return jsonify({'status': 'success', 'message': 'Conversation history cleared'})
        else:
            return jsonify({'status': 'error', 'message': 'RAG system not found'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@rag_bp.route('/reset_rag', methods=['POST'])
@login_required
def reset_rag():
    """
    Reset the RAG system (clear everything including persistent data)
    """
    try:
        company_id = session.get('user_id')
        rag_key = f'RAG_SYSTEM_{company_id}'

        # Get RAG system and delete all data
        rag_system = current_app.config.get(rag_key)
        if rag_system:
            rag_system.delete_company_data()

        # Clear session data
        session.pop('rag_system_initialized', None)
        session.pop('rag_system_ready', None)
        session.pop('uploaded_filename', None)
        session.pop('processed_file_path', None)

        # Clear RAG system from app config
        current_app.config.pop(rag_key, None)

        return jsonify({'status': 'success', 'message': 'RAG system reset successfully'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@rag_bp.route('/rag_status')
@login_required
def rag_status():
    """
    Check the status of the persistent RAG system
    """
    rag_system = get_or_create_rag_system()
    health_status = rag_system.health_check() if rag_system else {}

    return jsonify({
        'company_id': session.get('user_id'),
        'initialized': session.get('rag_system_initialized', False),
        'ready': session.get('rag_system_ready', False),
        'uploaded_file': session.get('uploaded_filename', None),
        'system_available': rag_system is not None,
        'llm_provider': 'groq',
        'health': health_status
    })

@rag_bp.route('/company_documents')
@login_required
def company_documents():
    """
    Get list of processed documents for the company
    """
    try:
        rag_system = get_or_create_rag_system()
        if rag_system:
            docs = rag_system.get_company_documents()
            return jsonify({
                'status': 'success',
                'documents': docs
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'RAG system not available'
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@rag_bp.route('/delete_document', methods=['POST'])
@login_required
def delete_document():
    """
    Delete a specific document and all its associated data
    """
    try:
        # Get RAG system for this company
        rag_system = get_or_create_rag_system()

        if rag_system is None:
            return jsonify({
                'status': 'error',
                'message': 'RAG system not available'
            }), 500

        # Get document file name from request
        data = request.get_json()
        if not data or 'file_name' not in data:
            return jsonify({
                'status': 'error',
                'message': 'File name not provided'
            }), 400

        file_name = data['file_name'].strip()
        if not file_name:
            return jsonify({
                'status': 'error',
                'message': 'File name cannot be empty'
            }), 400

        # Delete the document using RAG system
        result = rag_system.delete_document(file_name)

        if result['success']:
            # Update session if this was the only/current document
            remaining_docs = rag_system.get_company_documents()

            if not remaining_docs:
                # No documents left, update session
                session['rag_system_ready'] = False
                session.pop('uploaded_filename', None)
                session.pop('processed_file_path', None)

            return jsonify({
                'status': 'success',
                'message': result['message'],
                'deleted_items': result['deleted_items'],
                'remaining_documents': len(remaining_docs),
                'rag_system_ready': len(remaining_docs) > 0
            })
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 404

    except Exception as e:
        print(f"Document deletion error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error deleting document: {str(e)}'
        }), 500

@rag_bp.route('/delete_document_confirm/<file_name>', methods=['DELETE'])
@login_required
def delete_document_confirm(file_name):
    """
    Alternative endpoint for document deletion with file_name in URL
    """
    try:
        # Get RAG system for this company
        rag_system = get_or_create_rag_system()

        if rag_system is None:
            return jsonify({
                'status': 'error',
                'message': 'RAG system not available'
            }), 500

        # URL decode the file name
        from urllib.parse import unquote
        file_name = unquote(file_name)

        # Delete the document using RAG system
        result = rag_system.delete_document(file_name)

        if result['success']:
            # Update session if needed
            remaining_docs = rag_system.get_company_documents()

            if not remaining_docs:
                session['rag_system_ready'] = False
                session.pop('uploaded_filename', None)
                session.pop('processed_file_path', None)

            return jsonify({
                'status': 'success',
                'message': result['message'],
                'deleted_items': result['deleted_items'],
                'remaining_documents': len(remaining_docs)
            })
        else:
            return jsonify({
                'status': 'error',
                'message': result['error']
            }), 404

    except Exception as e:
        print(f"Document deletion error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error deleting document: {str(e)}'
        }), 500