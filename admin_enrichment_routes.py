"""
Admin routes for case enrichment and import workflow
Handles import, duplicate detection, enrichment, approval, and promotion
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, ImportedCaseStaging, FRCRModule, BodyPart, AgeGroup
from services import ImportService, DuplicateDetectionService, ConflictResolutionService, PromotionService
from access_control import require_admin
from datetime import datetime
import tempfile
import os
import json

enrichment_bp = Blueprint('enrichment', __name__, url_prefix='/api/admin/enrichment')


@enrichment_bp.before_request
@login_required
@require_admin
def check_admin():
    """Verify admin access for all enrichment endpoints"""
    pass


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
        backup_data = json.loads(file.read().decode('utf-8'))
        result = DuplicateDetectionService.check_duplicates(backup_data)
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
    
    return jsonify({
        'id': case.id,
        'case_number': case.case_number,
        'diagnosis': case.diagnosis,
        'questions': case.questions,
        'answers': case.answers,
        'discussion': case.discussion,
        'module': case.module.value if case.module else None,
        'body_part': case.body_part.value if case.body_part else None,
        'age_group': case.age_group.value if case.age_group else None,
        'is_public': case.is_public,
        'enrichment_status': case.enrichment_status,
        'enrichment_notes': case.enrichment_notes,
    }), 200


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


@enrichment_bp.route('/<int:case_id>/reject', methods=['POST'])
def reject_case(case_id):
    """Reject a case from import"""
    case = ImportedCaseStaging.query.get_or_404(case_id)
    data = request.get_json() or {}
    
    case.enrichment_status = 'rejected'
    case.enrichment_notes = data.get('reason', '')
    
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
