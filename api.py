"""
API Routes for Medical Claim Adjudication System
"""
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from processor import ClaimProcessor
import traceback

api_blueprint = Blueprint('api', __name__)

# Initialize processor (will be created per request to avoid state issues)
def get_processor():
    """Get a new processor instance with current app config"""
    policy_path = current_app.config.get('POLICY_PATH', 'policy.json')
    return ClaimProcessor(policy_path)

def allowed_file(filename):
    """Check if file extension is allowed"""
    allowed = os.getenv('ALLOWED_EXTENSIONS', 'pdf,jpg,jpeg,png,gif,bmp,txt').split(',')
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


@api_blueprint.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint
    
    Returns:
        JSON response with system status
    """
    try:
        policy_path = current_app.config.get('POLICY_PATH')
        policy_exists = os.path.exists(policy_path)
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'policy_loaded': policy_exists,
            'upload_folder': current_app.config.get('UPLOAD_FOLDER'),
            'max_file_size_mb': current_app.config.get('MAX_CONTENT_LENGTH', 0) // (1024 * 1024)
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@api_blueprint.route('/process-claim', methods=['POST'])
def process_claim():
    """
    Process a claim with multiple documents and return adjudication result
    
    Expected form data:
        - prescription: Prescription document (optional)
        - medical_bill: Medical bill document (optional)
        - pharmacy_bill: Pharmacy bill document (optional)
        - lab_results: Lab results document (optional)
        - claim_date: Claim submission date (YYYY-MM-DD) - optional
        - policy_id: Policy ID (optional)
        - member_id: Member ID (optional)
    
    Note: At least one document must be provided
    
    Returns:
        JSON response with adjudication result
    """
    file_paths = {}
    saved_files = []
    
    try:
        # Define allowed document types
        allowed_doc_types = ['prescription', 'medical_bill', 'pharmacy_bill', 
                            'lab_results', 'diagnostic_report']
        
        # Check if at least one file is provided
        has_files = any(doc_type in request.files for doc_type in allowed_doc_types)
        
        if not has_files:
            return jsonify({
                'error': 'No files provided',
                'message': f'Please upload at least one document. Allowed types: {", ".join(allowed_doc_types)}',
                'allowed_types': allowed_doc_types
            }), 400
        
        # Process each document type
        for doc_type in allowed_doc_types:
            if doc_type in request.files:
                file = request.files[doc_type]
                
                # Skip empty files
                if file.filename == '':
                    continue
                
                # Validate file type
                if not allowed_file(file.filename):
                    return jsonify({
                        'error': 'Invalid file type',
                        'message': f'File "{file.filename}" has invalid type',
                        'allowed_extensions': os.getenv("ALLOWED_EXTENSIONS"),
                        'document_type': doc_type
                    }), 400
                
                # Save file temporarily
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                unique_filename = f"{timestamp}_{doc_type}_{filename}"
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
                
                print(f"[ENDPOINT] Saving {doc_type} file to: {file_path}")
                file.save(file_path)
                print(f"[ENDPOINT] {doc_type} file saved successfully")
                
                file_paths[doc_type] = file_path
                saved_files.append(file_path)
        
        # Verify we have at least one valid file
        if not file_paths:
            return jsonify({
                'error': 'No valid files provided',
                'message': 'All uploaded files were empty or invalid'
            }), 400
        
        # Get optional parameters from form data
        claim_date = request.form.get('claim_date')
        if not claim_date:
            claim_date = datetime.now().strftime('%Y-%m-%d')
        
        # Validate date format
        try:
            datetime.strptime(claim_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({
                'error': 'Invalid date format',
                'message': 'Date must be in YYYY-MM-DD format',
                'provided_date': claim_date
            }), 400
        
        policy_id = request.form.get('policy_id')
        member_id = request.form.get('member_id')
        
        # Process the claim with multiple documents
        print(f"[ENDPOINT] Getting processor...")
        processor = get_processor()
        print(f"[ENDPOINT] Processing {len(file_paths)} documents: {list(file_paths.keys())}")
        print(f"[ENDPOINT] Calling process_claim_complete...")
        
        result = processor.process_claim_complete(
            file_paths=file_paths,
            claim_date=claim_date,
            policy_id=policy_id,
            member_id=member_id
        )
        
        print(f"[ENDPOINT] Processing complete, result decision: {result.get('decision')}")
        
        # Add processing metadata
        result['metadata'] = {
            'documents_processed': {
                doc_type: {
                    'filename': os.path.basename(path),
                    'file_size_bytes': os.path.getsize(path)
                }
                for doc_type, path in file_paths.items()
            },
            'processed_at': datetime.now().isoformat(),
            'total_documents': len(file_paths)
        }
        
        return jsonify({
            'success': True,
            'data': result
        }), 200
    
    except Exception as e:
        # Print full traceback to console
        print("\n" + "="*80)
        print("[ENDPOINT] EXCEPTION CAUGHT:")
        print("="*80)
        print(traceback.format_exc())
        print("="*80 + "\n")
        
        return jsonify({
            'error': 'Processing failed',
            'message': str(e),
            'type': type(e).__name__,
            'traceback': traceback.format_exc(),
            'timestamp': datetime.now().isoformat(),
            'documents_attempted': list(file_paths.keys()) if file_paths else []
        }), 500
    
    finally:
        # Clean up all uploaded files
        for file_path in saved_files:
            if os.path.exists(file_path):
                print(f"[ENDPOINT] Cleaning up file: {file_path}")
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"[ENDPOINT] Warning: Could not delete file: {e}")

@api_blueprint.route('/extract-data', methods=['POST'])
def extract_data():
    """
    Extract structured data from document without full adjudication
    
    Expected form data:
        - file: Document file (PDF, image, or text)
        - claim_date: Claim submission date (YYYY-MM-DD) - optional
    
    Returns:
        JSON response with extracted claim data
    """
    try:
        # Validate file presence
        if 'file' not in request.files:
            return jsonify({
                'error': 'No file provided',
                'message': 'Please upload a file'
            }), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                'error': 'Empty filename',
                'message': 'Please select a valid file'
            }), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                'error': 'Invalid file type',
                'message': f'Allowed types: {os.getenv("ALLOWED_EXTENSIONS")}',
                'filename': file.filename
            }), 400
        
        # Get claim date
        claim_date = request.form.get('claim_date')
        if not claim_date:
            claim_date = datetime.now().strftime('%Y-%m-%d')
        
        # Save file temporarily
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        
        try:
            # Extract data only
            processor = get_processor()
            document = processor.read_document(file_path)
            claim_data = processor.extract_claim_data(document, claim_date)
            
            return jsonify({
                'success': True,
                'data': claim_data,
                'metadata': {
                    'original_filename': filename,
                    'extracted_at': datetime.now().isoformat()
                }
            }), 200
            
        finally:
            # Clean up uploaded file
            if os.path.exists(file_path):
                os.remove(file_path)
    
    except Exception as e:
        return jsonify({
            'error': 'Extraction failed',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@api_blueprint.route('/validate-policy', methods=['GET'])
def validate_policy():
    """
    Validate that policy configuration is loaded and accessible
    
    Returns:
        JSON response with policy validation status
    """
    try:
        processor = get_processor()
        policy = processor.policy
        
        return jsonify({
            'valid': True,
            'policy_id': policy.get('policy_id', 'N/A'),
            'policy_start_date': policy.get('policy_start_date'),
            'policy_end_date': policy.get('policy_end_date'),
            'coverage_categories': list(policy.get('coverage_details', {}).keys()),
            'exclusions_count': len(policy.get('exclusions', [])),
            'timestamp': datetime.now().isoformat()
        }), 200
    
    except Exception as e:
        return jsonify({
            'valid': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@api_blueprint.errorhandler(413)
def file_too_large(e):
    """Handle file size exceeded error"""
    max_size = current_app.config.get('MAX_CONTENT_LENGTH', 0) // (1024 * 1024)
    return jsonify({
        'error': 'File too large',
        'message': f'Maximum file size is {max_size}MB',
        'timestamp': datetime.now().isoformat()
    }), 413


@api_blueprint.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return jsonify({
        'error': 'Endpoint not found',
        'message': 'The requested API endpoint does not exist',
        'timestamp': datetime.now().isoformat()
    }), 404


@api_blueprint.errorhandler(500)
def internal_error(e):
    """Handle internal server errors"""
    return jsonify({
        'error': 'Internal server error',
        'message': 'An unexpected error occurred',
        'timestamp': datetime.now().isoformat()
    }), 500