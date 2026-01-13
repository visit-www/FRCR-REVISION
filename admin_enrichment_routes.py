"""
Admin routes for case enrichment and import workflow
Handles import, duplicate detection, enrichment, approval, and promotion
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, ImportedCaseStaging, FRCRModule, BodyPart, AgeGroup, UserRole, User
from services import ImportService, DuplicateDetectionService, ConflictResolutionService, PromotionService
from datetime import datetime
import tempfile
import os
import json

enrichment_bp = Blueprint('enrichment', __name__, url_prefix='/api/admin/enrichment')


@enrichment_bp.before_request
@login_required
def check_admin():
    """Verify admin access for all enrichment endpoints"""
    # Skip for error handlers
    if request.endpoint and 'handle_' in request.endpoint:
        return
    
    # FRESH APPROACH: Skip complex admin check for duplicate check endpoint
    # This endpoint is read-only and doesn't modify data, so we can be more lenient
    if request.endpoint == 'enrichment.check_duplicates':
        # Just check if user is authenticated - duplicate check is safe for any authenticated user
        if not current_user.is_authenticated:
            return jsonify({'error': 'Unauthorized. Please log in.'}), 401
        # Allow any authenticated user to check duplicates (it's just a read operation)
        print(f"[ENRICHMENT] Allowing duplicate check for authenticated user: {current_user.email}")
        return
    
    # Debug: Log user info
    print(f"[ENRICHMENT] Checking admin access for user: {current_user.email if current_user.is_authenticated else 'NOT AUTHENTICATED'}")
    
    if not current_user.is_authenticated:
        print("[ENRICHMENT] User not authenticated")
        return jsonify({'error': 'Unauthorized. Please log in.'}), 401
    
    # Force refresh user from database to get latest role
    # Query directly from database to bypass any caching issues with PostgreSQL/Supabase
    user_from_db = None
    try:
        # Query user directly from database to ensure we get the latest role
        # This is important for PostgreSQL where enum values might be cached
        user_from_db = User.query.get(current_user.id)
        if not user_from_db:
            print(f"[ENRICHMENT] ERROR: User {current_user.id} not found in database")
            return jsonify({'error': 'User not found in database'}), 403
        
        # Update current_user with fresh data
        db.session.expire(current_user)
        db.session.refresh(current_user)
        
        # Use the directly queried user's role for comparison (most reliable)
        user_role = user_from_db.role
        
        print(f"[ENRICHMENT] User role from DB query: {user_from_db.role}, type: {type(user_from_db.role).__name__}")
        print(f"[ENRICHMENT] User role from current_user: {current_user.role}, type: {type(current_user.role).__name__}")
    except Exception as e:
        print(f"[ENRICHMENT] Error querying user from database: {e}")
        import traceback
        traceback.print_exc()
        # Fallback to current_user
        user_role = current_user.role
    
    print(f"[ENRICHMENT] Raw role: {user_role}, type: {type(user_role).__name__}")
    
    # Handle string role (shouldn't happen but be defensive)
    if isinstance(user_role, str):
        print(f"[ENRICHMENT] Role is string '{user_role}', converting to enum")
        try:
            user_role = UserRole(user_role.lower())
            current_user.role = user_role
            db.session.commit()
            print(f"[ENRICHMENT] Converted to enum: {user_role}")
        except (ValueError, KeyError) as e:
            print(f"[ENRICHMENT] Error converting role string to enum: {e}")
            return jsonify({'error': 'Access denied. Invalid user role.'}), 403
    
    # Check if it's a UserRole enum
    if not isinstance(user_role, UserRole):
        print(f"[ENRICHMENT] ERROR: Role is not UserRole enum! Type: {type(user_role).__name__}, Value: {user_role}")
        # Try to get role by value
        try:
            if hasattr(user_role, 'value'):
                role_value = user_role.value
            else:
                role_value = str(user_role)
            user_role = UserRole(role_value)
            current_user.role = user_role
            db.session.commit()
            print(f"[ENRICHMENT] Fixed role to enum: {user_role}")
        except Exception as e:
            print(f"[ENRICHMENT] Could not fix role: {e}")
            return jsonify({'error': 'Access denied. Please ensure you are logged in as an admin.'}), 403
    
    # Compare with ADMIN enum - handle case differences between DB and Python
    # PostgreSQL stores enum as 'ADMIN' (uppercase), Python enum value is 'admin' (lowercase)
    is_admin = False
    
    # Method 1: Direct enum comparison
    if isinstance(user_role, UserRole):
        is_admin = user_role == UserRole.ADMIN
        print(f"[ENRICHMENT] Direct enum comparison: {is_admin}")
    
    # Method 2: Value comparison (case-insensitive) - handles DB storing 'ADMIN' vs Python 'admin'
    if not is_admin:
        role_value = user_role.value.lower() if hasattr(user_role, 'value') and isinstance(user_role, UserRole) else str(user_role).lower()
        admin_value = UserRole.ADMIN.value.lower()
        is_admin = role_value == admin_value
        print(f"[ENRICHMENT] Case-insensitive value comparison: '{role_value}' == '{admin_value}'? {is_admin}")
    
    # Method 3: Check raw database value (PostgreSQL stores as 'ADMIN' uppercase)
    if not is_admin and user_from_db:
        try:
            from sqlalchemy import text
            result = db.session.execute(text("SELECT role::text FROM \"user\" WHERE id = :user_id"), {"user_id": user_from_db.id})
            db_role_raw = result.scalar()
            if db_role_raw:
                db_role_lower = str(db_role_raw).lower()
                if db_role_lower == 'admin':
                    print(f"[ENRICHMENT] Database raw value check: '{db_role_raw}' -> '{db_role_lower}' == 'admin'")
                    is_admin = True
        except Exception as e:
            print(f"[ENRICHMENT] Could not check raw DB value: {e}")
    
    print(f"[ENRICHMENT] Final admin check result: {is_admin}")
    print(f"[ENRICHMENT] Role value: '{user_role.value if hasattr(user_role, 'value') else user_role}', ADMIN value: '{UserRole.ADMIN.value}'")
    
    if not is_admin:
        print(f"[ENRICHMENT] Access denied: role '{user_role.value if hasattr(user_role, 'value') else user_role}' != ADMIN '{UserRole.ADMIN.value}'")
        # Return more detailed error for debugging
        return jsonify({
            'error': 'Access denied. Please ensure you are logged in as an admin.',
            'debug': {
                'user_email': current_user.email,
                'role_type': type(user_role).__name__,
                'role_value': user_role.value if hasattr(user_role, 'value') else str(user_role),
                'expected': UserRole.ADMIN.value
            }
        }), 403
    
    print(f"[ENRICHMENT] ✓ Admin access granted for {current_user.email}")


@enrichment_bp.errorhandler(401)
def handle_401(error):
    """Return JSON error for 401 Unauthorized"""
    return jsonify({'error': 'Unauthorized. Please log in.'}), 401


@enrichment_bp.errorhandler(403)
def handle_403(error):
    """Return JSON error for 403 Forbidden"""
    return jsonify({'error': 'Access denied. Admin privileges required.'}), 403


@enrichment_bp.errorhandler(404)
def handle_404(error):
    """Return JSON error for 404 Not Found"""
    return jsonify({'error': 'Endpoint not found'}), 404


# ============================================================================
# IMPORT & DUPLICATE DETECTION ENDPOINTS
# ============================================================================

@enrichment_bp.route('/check-duplicates', methods=['POST'])
def check_duplicates():
    """
    Scan backup file for duplicates before importing
    Returns report of conflicts
    
    Body: multipart/form-data with 'backup_file'
    Returns: {total_cases, new_cases, duplicates_in_staging, duplicates_in_production}
    """
    if 'backup_file' not in request.files:
        return jsonify({'error': 'No backup file provided'}), 400
    
    file = request.files['backup_file']
    if not file.filename.endswith('.json'):
        return jsonify({'error': 'Only JSON files supported'}), 400
    
    try:
        # FRESH APPROACH: Handle large files by reading in chunks
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        print(f"[DUPLICATE CHECK] Backup file size: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)")
        
        # Read file in chunks to handle large files (26MB+)
        file_content_parts = []
        chunk_size = 1024 * 1024  # 1MB chunks
        total_read = 0
        
        while True:
            chunk = file.read(chunk_size)
            if not chunk:
                break
            file_content_parts.append(chunk)
            total_read += len(chunk)
            print(f"[DUPLICATE CHECK] Read chunk: {total_read / 1024 / 1024:.2f} MB / {file_size / 1024 / 1024:.2f} MB")
        
        # Combine chunks
        file_content = b''.join(file_content_parts)
        if not file_content:
            return jsonify({'error': 'Backup file is empty'}), 400
        
        # Clear file reference to prevent multiple reads
        file = None
        file_content_parts = None
        
        try:
            file_text = file_content.decode('utf-8')
        except UnicodeDecodeError as e:
            return jsonify({'error': f'Invalid file encoding: {str(e)}'}), 400
        
        # Parse JSON
        try:
            backup_data = json.loads(file_text)
        except json.JSONDecodeError as e:
            return jsonify({'error': f'Invalid JSON format: {str(e)}'}), 400
        
        # Validate backup structure
        if not isinstance(backup_data, dict):
            return jsonify({'error': 'Backup file must contain a JSON object'}), 400
        
        if 'cases' not in backup_data:
            return jsonify({'error': 'Backup file missing "cases" array'}), 400
        
        # Check for duplicates
        try:
            result = DuplicateDetectionService.check_duplicates(backup_data)
            return jsonify(result), 200
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Error checking duplicates: {str(e)}'}), 500
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500


@enrichment_bp.route('/import', methods=['POST'])
def import_cases():
    """
    Import cases from backup JSON file (without checking duplicates)
    
    Body: multipart/form-data with 'backup_file'
    Returns: {import_batch_id, total_imported, errors}
    """
    if 'backup_file' not in request.files:
        return jsonify({'error': 'No backup file provided'}), 400
    
    file = request.files['backup_file']
    if not file.filename.endswith('.json'):
        return jsonify({'error': 'Only JSON files supported'}), 400
    
    try:
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp:
            file.save(tmp.name)
            result = ImportService.import_from_backup(tmp.name)
            os.unlink(tmp.name)
        
        # Ensure response includes imported_count for UI
        if 'total_imported' in result:
            result['imported_count'] = result['total_imported']
        
        return jsonify(result), 200 if result['success'] else 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@enrichment_bp.route('/conflicts/<int:original_id>', methods=['GET'])
def get_duplicate_conflicts(original_id):
    """Get all versions of a case (staging + production)"""
    result = DuplicateDetectionService.get_duplicate_conflicts(original_id)
    return jsonify(result), 200


@enrichment_bp.route('/resolve-duplicate', methods=['POST'])
def resolve_duplicate():
    """
    Admin decides how to handle a duplicate
    
    Body: {
        original_id: int,
        new_case_data: {...},
        resolution_strategy: 'skip'|'replace'|'update'|'create_new'|'force_import'
    }
    """
    data = request.get_json()
    
    result = ConflictResolutionService.resolve_duplicate(
        original_id=data['original_id'],
        new_case_data=data.get('new_case_data'),
        resolution_strategy=data['resolution_strategy'],
        user_id=current_user.id
    )
    
    return jsonify(result), 200 if result['success'] else 400


# ============================================================================
# ENRICHMENT ENDPOINTS
# ============================================================================

@enrichment_bp.route('/pending', methods=['GET'])
def get_pending_cases():
    """
    Get list of cases pending enrichment
    
    Query Parameters:
    - page: int (default 1)
    - per_page: int (default 20)
    
    Returns: {cases, total, pages, current_page}
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    pagination = ImportService.get_pending_cases(page, per_page)
    
    return jsonify({
        'cases': [{
            'id': case.id,
            'case_number': case.case_number,
            'diagnosis': case.diagnosis[:100],
            'module': case.module.value if case.module else None,
            'body_part': case.body_part.value if case.body_part else None,
            'age_group': case.age_group.value if case.age_group else None,
            'is_public': case.is_public,
            'enrichment_status': case.enrichment_status,
        } for case in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    }), 200


@enrichment_bp.route('/<int:case_id>', methods=['GET'])
def get_case_details(case_id):
    """Get full details of a case for enrichment"""
    case = ImportedCaseStaging.query.get_or_404(case_id)
    
    # Convert case_number to string if it's an integer
    case_number_str = str(case.case_number) if case.case_number else None
    
    # Extract images from enrichment_notes if present
    # Format: [IMAGES_JSON]{...}[/IMAGES_JSON] in enrichment_notes
    images = []
    if case.enrichment_notes:
        import re
        import json as json_lib
        
        print(f"[ENRICH] Checking enrichment_notes for case {case_id}, length: {len(case.enrichment_notes)}")
        
        # Try to find IMAGES_JSON marker - use non-greedy match with DOTALL
        # Pattern: [IMAGES_JSON]...[/IMAGES_JSON]
        images_match = re.search(r'\[IMAGES_JSON\](.*?)\[/IMAGES_JSON\]', case.enrichment_notes, re.DOTALL | re.MULTILINE)
        if not images_match:
            # Try without DOTALL in case of formatting issues
            images_match = re.search(r'\[IMAGES_JSON\](.*?)\[/IMAGES_JSON\]', case.enrichment_notes)
        
        if images_match:
            print(f"[ENRICH] Found IMAGES_JSON marker for case {case_id}")
            try:
                images_json_str = images_match.group(1).strip()
                print(f"[ENRICH] Extracted JSON string length: {len(images_json_str)}")
                images_data = json_lib.loads(images_json_str)
                print(f"[ENRICH] Parsed {len(images_data)} images from JSON")
                
                # Convert images to displayable format
                # Create temporary IDs for display (they'll get real IDs on promotion)
                for idx, img_data in enumerate(images_data):
                    if not isinstance(img_data, dict):
                        print(f"[ENRICH] Warning: Image {idx} is not a dict, skipping")
                        continue
                    
                    image_data_base64 = img_data.get('image_data')
                    if not image_data_base64:
                        print(f"[ENRICH] Warning: Image {idx} has no image_data, skipping")
                        continue
                    
                    images.append({
                        'id': f'staging-{case_id}-img-{idx}',  # Temporary ID for display
                        'filename': img_data.get('filename', 'image'),
                        'image_filename': img_data.get('filename', 'image'),  # For compatibility
                        'description': img_data.get('description', ''),
                        'image_description': img_data.get('description', ''),  # For compatibility
                        'image_type': img_data.get('image_type', 'image/jpeg'),
                        'image_data': image_data_base64,  # Base64 string for data URL
                        'is_staging': True  # Flag to indicate this is a staging image
                    })
                    print(f"[ENRICH] Added image {idx}: {img_data.get('filename', 'unknown')} (data length: {len(image_data_base64) if image_data_base64 else 0})")
                
                print(f"[ENRICH] Total images extracted: {len(images)}")
            except (json_lib.JSONDecodeError, Exception) as e:
                print(f"[ENRICH] Error parsing images JSON from staging case {case_id}: {e}")
                import traceback
                traceback.print_exc()
        else:
            # No IMAGES_JSON marker found - this could mean:
            # 1. Case was imported before image storage logic was added
            # 2. Images weren't found during import
            # 3. Images are stored in a different format
            print(f"[ENRICH] No IMAGES_JSON marker found in enrichment_notes for case {case_id}")
            
            # Check if case has original_id - if so, we might be able to find images in the backup
            if case.original_id and case.source_system == 'frcr_examiner':
                print(f"[ENRICH] Case has original_id={case.original_id}, source_system={case.source_system}")
                print(f"[ENRICH] Images may not have been stored during import - case may need to be re-imported")
            
            # Debug: show first 500 chars of enrichment_notes
            preview = case.enrichment_notes[:500] if len(case.enrichment_notes) > 500 else case.enrichment_notes
            print(f"[ENRICH] Enrichment notes preview: {preview}...")
            
            # Also check if IMAGES_JSON exists but with different formatting
            if '[IMAGES_JSON]' in case.enrichment_notes or 'IMAGES_JSON' in case.enrichment_notes:
                print(f"[ENRICH] Found IMAGES_JSON text but regex didn't match - checking format...")
                # Try alternative patterns
                alt_patterns = [
                    r'\[IMAGES_JSON\](.*?)\[/IMAGES_JSON\]',
                    r'IMAGES_JSON(.*?)IMAGES_JSON',
                    r'\[IMAGES_JSON\](.*)',
                ]
                for pattern in alt_patterns:
                    alt_match = re.search(pattern, case.enrichment_notes, re.DOTALL)
                    if alt_match:
                        print(f"[ENRICH] Alternative pattern matched: {pattern[:30]}...")
                        break
    
    # Debug information (remove in production)
    debug_info = {
        'has_enrichment_notes': bool(case.enrichment_notes),
        'enrichment_notes_length': len(case.enrichment_notes) if case.enrichment_notes else 0,
        'has_images_json_marker': '[IMAGES_JSON]' in (case.enrichment_notes or ''),
        'images_extracted_count': len(images),
        'enrichment_notes_preview': (case.enrichment_notes[:200] + '...' if case.enrichment_notes and len(case.enrichment_notes) > 200 else case.enrichment_notes) if case.enrichment_notes else None
    }
    
    return jsonify({
        'id': case.id,
        'case_number': case_number_str,
        'diagnosis': case.diagnosis,
        'questions': case.questions,
        'answers': case.answers,
        'discussion': case.discussion,
        'module': case.module.name if case.module else None,  # Return enum name, not value
        'body_part': case.body_part.name if case.body_part else None,  # Return enum name, not value
        'age_group': case.age_group.name if case.age_group else None,  # Return enum name, not value
        'status': getattr(case, 'status', None) and case.status.name if hasattr(case, 'status') and case.status else 'DRAFT',
        'is_public': case.is_public,
        'enrichment_status': case.enrichment_status,
        'enrichment_notes': case.enrichment_notes,
        'images': images,  # Include extracted images
        '_debug': debug_info  # Debug info to help diagnose issues
    }), 200


@enrichment_bp.route('/<int:case_id>/public', methods=['PATCH'])
def toggle_staging_case_public(case_id):
    """
    Toggle the public/private status of a staging case
    
    Body: { is_public: true/false }
    Returns: { success: bool, is_public: bool }
    """
    staging = ImportedCaseStaging.query.get_or_404(case_id)
    data = request.get_json()
    is_public = data.get('is_public')
    
    # Robustly handle boolean and string values
    if isinstance(is_public, str):
        is_public = is_public.lower() == 'true'
    else:
        is_public = bool(is_public)
    
    try:
        staging.is_public = is_public
        db.session.commit()
        return jsonify({'success': True, 'is_public': staging.is_public}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Database error', 'details': str(e)}), 500


@enrichment_bp.route('/<int:case_id>', methods=['DELETE'])
def delete_staging_case(case_id):
    """
    Delete a staging case (does not affect source database)
    
    Returns: { success: bool, message: str }
    """
    staging = ImportedCaseStaging.query.get_or_404(case_id)
    
    try:
        db.session.delete(staging)
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Staging case deleted successfully'
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'Failed to delete staging case: {str(e)}'
        }), 500


@enrichment_bp.route('/bulk-delete', methods=['DELETE'])
def bulk_delete_staging_cases():
    """
    Delete all staging cases (bulk operation)
    Query parameters:
    - status: optional filter by status (pending, enriched, rejected)
    """
    try:
        status_filter = request.args.get('status', None)
        
        # Build query
        query = ImportedCaseStaging.query
        if status_filter:
            query = query.filter_by(enrichment_status=status_filter)
        
        # Count cases to be deleted
        count = query.count()
        
        if count == 0:
            return jsonify({
                'success': True,
                'message': 'No staging cases to delete',
                'deleted_count': 0
            }), 200
        
        # Delete all matching cases
        deleted = query.delete(synchronize_session=False)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Successfully deleted {deleted} staging case(s)',
            'deleted_count': deleted
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'Failed to delete staging cases: {str(e)}'
        }), 500


@enrichment_bp.route('/<int:case_id>/enrich', methods=['PUT'])
def enrich_case(case_id):
    """
    Update case with enrichment metadata
    
    Body: {
        module: str (enum value),
        body_part: str (enum value),
        age_group: str (enum value),
        is_public: bool,
        enrichment_notes: str
    }
    """
    case = ImportedCaseStaging.query.get_or_404(case_id)
    data = request.get_json()
    
    try:
        # Update enums
        if data.get('module'):
            case.module = FRCRModule(data['module'])
        
        if data.get('body_part'):
            case.body_part = BodyPart(data['body_part'])
        
        if data.get('age_group'):
            case.age_group = AgeGroup(data['age_group'])
        
        # Update public flag
        case.is_public = data.get('is_public', False)
        
        # Mark as enriched
        case.enrichment_status = 'enriched'
        case.enriched_by_user_id = current_user.id
        case.enriched_at = datetime.utcnow()
        case.enrichment_notes = data.get('enrichment_notes', '')
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Case enriched'}), 200
        
    except ValueError as e:
        return jsonify({'error': f'Invalid enum value: {str(e)}'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@enrichment_bp.route('/<int:case_id>/approve', methods=['POST'])
def approve_case(case_id):
    """
    Admin approves enriched case for promotion to production
    
    Body: { approval_notes: str (optional) }
    """
    case = ImportedCaseStaging.query.get_or_404(case_id)
    
    if case.enrichment_status != 'enriched':
        return jsonify({
            'error': 'Only enriched cases can be approved'
        }), 400
    
    data = request.get_json() or {}
    
    try:
        case.approved_by_user_id = current_user.id
        case.approved_at = datetime.utcnow()
        case.approval_notes = data.get('approval_notes', '')
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Case approved'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@enrichment_bp.route('/<int:case_id>/enrich-and-promote', methods=['PUT'])
def enrich_and_promote_case(case_id):
    """
    Update staging case with enrichment metadata and immediately promote to production
    Used when admin completes missing fields during import review
    
    Body: {
        module: str (enum value),
        body_part: str (enum value),
        age_group: str (enum value),
        is_public: bool,
        status: str (DRAFT, PUBLISHED, etc.),
        case_number: str,
        diagnosis: str,
        discussion: str,
        pairs: [{'question_text': str, 'answer_text': str}]
    }
    """
    from models import Case, Question, Answer, CaseStatus
    import json
    
    staging = ImportedCaseStaging.query.get_or_404(case_id)
    data = request.get_json()
    
    try:
        # Update enums (form sends enum names, not values)
        if data.get('module'):
            try:
                staging.module = FRCRModule[data['module']]  # Access by enum name
            except (KeyError, AttributeError) as e:
                print(f"[ENRICH] Error setting module '{data['module']}': {e}")
                raise ValueError(f"Invalid module value: '{data['module']}'. Valid values: {[m.name for m in FRCRModule]}")
        
        if data.get('body_part'):
            try:
                staging.body_part = BodyPart[data['body_part']]  # Access by enum name
            except (KeyError, AttributeError) as e:
                print(f"[ENRICH] Error setting body_part '{data['body_part']}': {e}")
                raise ValueError(f"Invalid body_part value: '{data['body_part']}'. Valid values: {[bp.name for bp in BodyPart]}")
        
        if data.get('age_group'):
            try:
                staging.age_group = AgeGroup[data['age_group']]  # Access by enum name
            except (KeyError, AttributeError) as e:
                print(f"[ENRICH] Error setting age_group '{data['age_group']}': {e}")
                raise ValueError(f"Invalid age_group value: '{data['age_group']}'. Valid values: {[ag.name for ag in AgeGroup]}")
        
        # Update other fields
        if data.get('case_number'):
            staging.case_number = data['case_number']
        if data.get('diagnosis'):
            staging.diagnosis = data['diagnosis']
        if data.get('discussion') is not None:
            staging.discussion = data['discussion']
        
        staging.is_public = data.get('is_public', False)
        staging.enrichment_status = 'enriched'
        staging.enriched_by_user_id = current_user.id
        staging.enriched_at = datetime.utcnow()
        
        # Convert case_number to proper format if body_part is set
        case_number = data.get('case_number') or staging.case_number
        if data.get('body_part') and case_number:
            try:
                # body_part was already set above using BodyPart[data['body_part']]
                body_part_enum = staging.body_part
                if not body_part_enum:
                    body_part_enum = BodyPart[data['body_part']]
                # If case_number is numeric, convert to bodypart-00<number> format
                if isinstance(case_number, int) or (isinstance(case_number, str) and case_number.replace('-', '').isdigit()):
                    # Extract number (handle both "123" and "chest-123")
                    import re
                    num_match = re.search(r'(\d+)$', str(case_number))
                    if num_match:
                        num = int(num_match.group(1))
                        body_part_name = body_part_enum.value.lower().replace('_', '').replace(' ', '')
                        body_part_short = body_part_name[:6]
                        case_number_formatted = f"{body_part_short}-{num:03d}"
                        # Store formatted version in enrichment_notes (staging.case_number is Integer)
                        if staging.enrichment_notes:
                            staging.enrichment_notes = f"[CASE_NUMBER_FORMATTED]{case_number_formatted}[/CASE_NUMBER_FORMATTED]\n{staging.enrichment_notes}"
                        else:
                            staging.enrichment_notes = f"[CASE_NUMBER_FORMATTED]{case_number_formatted}[/CASE_NUMBER_FORMATTED]"
                        # Also store numeric part in case_number field
                        staging.case_number = num
            except (ValueError, AttributeError) as e:
                print(f"[ENRICH] Warning: Could not convert case_number format: {e}")
        
        # Promote to production (bypass approval requirement for direct enrich-and-promote)
        # Temporarily mark as approved if not already
        if not staging.approved_at:
            staging.approved_by_user_id = current_user.id
            staging.approved_at = datetime.utcnow()
            staging.approval_notes = 'Auto-approved during enrich-and-promote'
        
        # Ensure status is enriched
        if staging.enrichment_status != 'enriched':
            staging.enrichment_status = 'enriched'
        
        # Check for duplicate diagnoses before promoting (unless override flag is set)
        diagnosis = data.get('diagnosis') or staging.diagnosis
        override_duplicate = data.get('override_duplicate', False)
        
        if diagnosis and not override_duplicate:
            # Normalize diagnosis for comparison (lowercase, strip whitespace)
            normalized_diagnosis = diagnosis.lower().strip()
            
            # Check for exact matches in existing cases (both public and private)
            # Exclude rejected cases - they shouldn't block new cases
            existing_cases = Case.query.filter(
                db.func.lower(db.func.trim(Case.diagnosis)) == normalized_diagnosis
            ).filter(
                Case.status != CaseStatus.REJECTED
            ).all()
            
            if existing_cases:
                # Exact match found - return duplicate information
                duplicate_info = []
                for existing_case in existing_cases:
                    duplicate_info.append({
                        'id': existing_case.id,
                        'diagnosis': existing_case.diagnosis,
                        'module': existing_case.module.value if existing_case.module else 'N/A',
                        'is_public': existing_case.is_public,
                        'status': existing_case.status.value if hasattr(existing_case, 'status') and existing_case.status else 'N/A'
                    })
                
                return jsonify({
                    'success': False,
                    'duplicate': True,
                    'exact_match': True,
                    'message': f'Exact duplicate diagnosis found: "{diagnosis}"',
                    'existing_cases': duplicate_info,
                    'new_diagnosis': diagnosis
                }), 409  # 409 Conflict
            
            # Check for similar diagnoses (case-insensitive contains or similarity)
            # Check if normalized diagnosis is contained in any existing diagnosis or vice versa
            # Exclude rejected cases - they shouldn't block new cases
            similar_cases = Case.query.filter(
                db.or_(
                    db.func.lower(Case.diagnosis).contains(normalized_diagnosis),
                    db.func.lower(db.func.cast(diagnosis, db.String)).contains(db.func.lower(Case.diagnosis))
                )
            ).filter(
                Case.status != CaseStatus.REJECTED
            ).all()
            
            # Filter out exact matches (already handled above) and very short matches
            similar_cases = [
                c for c in similar_cases 
                if c.diagnosis.lower().strip() != normalized_diagnosis 
                and len(normalized_diagnosis) > 5  # Only flag if diagnosis is meaningful length
            ]
            
            if similar_cases:
                # Similar match found - return duplicate information for user to decide
                similar_info = []
                for similar_case in similar_cases:
                    similar_info.append({
                        'id': similar_case.id,
                        'diagnosis': similar_case.diagnosis,
                        'module': similar_case.module.value if similar_case.module else 'N/A',
                        'is_public': similar_case.is_public,
                        'status': similar_case.status.value if hasattr(similar_case, 'status') and similar_case.status else 'N/A'
                    })
                
                return jsonify({
                    'success': False,
                    'duplicate': True,
                    'exact_match': False,
                    'message': f'Similar diagnosis found: "{diagnosis}"',
                    'existing_cases': similar_info,
                    'new_diagnosis': diagnosis
                }), 409  # 409 Conflict
        
        db.session.flush()
        
        # Get target status from request or default
        target_status = CaseStatus.DRAFT
        if data.get('status'):
            try:
                target_status = CaseStatus[data['status']]
            except (KeyError, AttributeError):
                target_status = CaseStatus.DRAFT if not staging.is_public else CaseStatus.PUBLISHED
        
        result = PromotionService.promote_case(case_id, created_by_user_id=current_user.id, target_status=target_status)
        
        if not result['success']:
            return jsonify({'error': result.get('error', 'Promotion failed')}), 400
        
        promoted_case_id = result['case_id']
        
        # Ensure case is mapped to current user (for FRCR Examiner imports)
        # This ensures that when cases are promoted, they're owned by the user who promoted them
        promoted_case = Case.query.get(promoted_case_id)
        if promoted_case:
            # Check if this is from FRCR Examiner import (source_system = 'frcr_examiner')
            if staging.source_system == 'frcr_examiner':
                promoted_case.created_by_user_id = current_user.id
                print(f"[ENRICH] Mapped promoted case {promoted_case_id} to current user {current_user.id} (FRCR Examiner import)")
        
        # Update Q&A pairs if provided
        if data.get('pairs'):
            # Delete existing Q&A for the promoted case
            Question.query.filter_by(case_id=promoted_case_id).delete()
            Answer.query.filter_by(case_id=promoted_case_id).delete()
            
            # Add new Q&A pairs
            for idx, pair in enumerate(data['pairs'], 1):
                if pair.get('question_text'):
                    question = Question(
                        case_id=promoted_case_id,
                        question_number=idx,
                        question_text=pair['question_text']
                    )
                    db.session.add(question)
                
                if pair.get('answer_text'):
                    answer = Answer(
                        case_id=promoted_case_id,
                        answer_number=idx,
                        answer_text=pair['answer_text']
                    )
                    db.session.add(answer)
        
        # Handle images from backup if stored in staging enrichment_notes
        # Format: [IMAGES_JSON]{...}[/IMAGES_JSON] in enrichment_notes
        from models import CaseImage
        import base64
        import re
        
        if staging.enrichment_notes:
            # Extract images JSON from enrichment_notes
            images_match = re.search(r'\[IMAGES_JSON\](.*?)\[/IMAGES_JSON\]', staging.enrichment_notes, re.DOTALL)
            if images_match:
                try:
                    images_json_str = images_match.group(1)
                    images_data = json.loads(images_json_str)
                    
                    for img_data in images_data:
                        try:
                            if img_data.get('image_data'):
                                # Decode base64 image data
                                image_data_binary = base64.b64decode(img_data['image_data'])
                                
                                # Create CaseImage
                                case_image = CaseImage(
                                    case_id=promoted_case_id,
                                    image_filename=img_data.get('filename', 'image'),
                                    image_type=img_data.get('image_type', 'image/jpeg'),
                                    image_description=img_data.get('description', ''),
                                    image_data=image_data_binary
                                )
                                db.session.add(case_image)
                        except Exception as img_err:
                            print(f"[ENRICH] Warning: Failed to migrate image: {img_err}")
                except (json.JSONDecodeError, Exception) as e:
                    print(f"[ENRICH] Warning: Could not parse images JSON: {e}")
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Case enriched and promoted to production',
            'case_id': promoted_case_id,
            'id': promoted_case_id  # Also include 'id' for compatibility
        }), 200
        
    except ValueError as e:
        return jsonify({'error': f'Invalid enum value: {str(e)}'}), 400
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@enrichment_bp.route('/<int:case_id>/reject', methods=['POST'])
def reject_case(case_id):
    """Reject a case from import"""
    case = ImportedCaseStaging.query.get_or_404(case_id)
    data = request.get_json() or {}
    
    case.enrichment_status = 'rejected'
    case.enrichment_notes = data.get('reason', '')
    # Track who rejected it (for FRCR Examiner imports, this ensures ownership tracking)
    case.enriched_by_user_id = current_user.id
    case.enriched_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({'success': True}), 200


# ============================================================================
# PROMOTION ENDPOINTS
# ============================================================================

@enrichment_bp.route('/<int:case_id>/promote', methods=['POST'])
def promote_case(case_id):
    """Promote single case to production"""
    result = PromotionService.promote_case(case_id, current_user.id)
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@enrichment_bp.route('/batch/<batch_id>/promote-all', methods=['POST'])
def bulk_promote_batch(batch_id):
    """Promote all approved cases in a batch to production"""
    result = PromotionService.bulk_promote(batch_id, current_user.id)
    return jsonify(result), 200


# ============================================================================
# STATISTICS ENDPOINTS
# ============================================================================

@enrichment_bp.route('/stats', methods=['GET'])
def get_stats():
    """Get enrichment statistics"""
    batch_id = request.args.get('batch_id')
    stats = ImportService.get_enrichment_stats(batch_id)
    
    return jsonify(stats), 200
