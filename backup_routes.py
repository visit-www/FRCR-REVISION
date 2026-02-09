"""
Database Backup and Restore Routes for Web Deployment
Handles manual backup downloads and restore from uploads
"""
from flask import Blueprint, jsonify, send_file, request, session
from flask_login import login_required, current_user
from models import (
    db, User, Case, CaseImage, Question, Answer,
    RevisionSession, RevisionHistory, CaseFlag, TextHighlight, CandidateNote,
    ImportedCaseStaging, UserRole, FRCRModule, BodyPart, AgeGroup,
    SubscriptionStatus, PaymentStatus, CaseStatus,
    ForumMessage, ForumMessageVote, ForumMessageFlag,
    CaseReference, CaseReferenceImage, TnmReference, AnatomyFigure, TNMImage,
    # Audit, analytics and approval models
    CaseAuditLog, CaseViewLog, CaseApprovalQueue,
    # Spaced repetition progress
    UserQAProgress,
    # AI cache
    AiDiagnosisCache, AiPrelimCaseData,
    # Association tables
    related_cases, case_calculator_links, case_reference_links,
    # AJCC TNM Models
    AJCCBodySection, AJCCDiseaseSite, AJCCDiagnosisYear,
    AJCCStagingData, AJCCDiseaseMapping, AJCCStagingTimePrefix,
    IntelligentTNMData,
    # Case DICOM Viewer Models
    CaseImageStack, CaseImageAnnotation,
    # TNM Calculator Content (AI-generated calculators and algorithms)
    TNMCalculatorContent,
    # Clinical Tools (On-Call Helper, Reporting Templates, Incidental Findings)
    ClinicalProtocol, OnCallQueryLog, ReportingTemplate,
    IncidentalFindingCalculator,
)
from datetime import datetime, timedelta
from sqlalchemy import inspect
import json
import io
import os
import uuid

backup_bp = Blueprint('backup', __name__, url_prefix='/api/backup')

def check_admin():
    """Check if current user is admin (Content Managers do NOT have backup access)"""
    try:
        if not current_user.is_authenticated:
            return False
        # Only admins can access backup/restore functionality
        return (hasattr(current_user, 'role') and 
                current_user.role == UserRole.ADMIN)
    except Exception as e:
        return False

def get_model_fields(model_class):
    """Get all column names for a model class"""
    return [column.name for column in inspect(model_class).columns]

def _parse_datetime_for_sqlite(value):
    """Parse value to naive Python datetime for SQLite compatibility.
    SQLite rejects timezone-aware datetimes."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, str) and value.strip():
        try:
            s = value.replace('Z', '+00:00')
            dt = datetime.fromisoformat(s)
            return dt.replace(tzinfo=None) if dt.tzinfo else dt
        except (ValueError, TypeError):
            return None
    return None

@backup_bp.route('/download', methods=['GET'])
@login_required
def download_backup():
    """Download complete database backup as JSON"""
    if not check_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    try:
        # Collect all data
        backup_data = {
            'metadata': {
                'backup_date': datetime.utcnow().isoformat(),
                'database_type': 'postgresql' if os.getenv('DATABASE_URL') or os.getenv('DATABASE_POSTGRES_URL_NON_POOLING') else 'sqlite',
                'version': '2.9',  # Bumped for clinical tools tables
                'app_name': 'RadInsights'
            },
            'users': [],
            'cases': [],
            'case_images': [],
            'questions': [],
            'answers': [],
            'revision_sessions': [],
            'revision_history': [],  # NEW: User progress tracking
            'case_flags': [],
            'highlights': [],
            'notes': [],
            # Forum data (critical for discussions)
            'forum_messages': [],
            'forum_votes': [],
            'forum_flags': [],
            # AJCC TNM Staging data
            'ajcc_body_sections': [],
            'ajcc_disease_sites': [],
            'ajcc_diagnosis_years': [],
            'ajcc_staging_data': [],
            'ajcc_disease_mappings': [],
            'ajcc_staging_time_prefixes': [],
            'intelligent_tnm_data': [],  # AI-generated TNM intelligence
            # Reference and media tables
            'case_references': [],
            'case_reference_images': [],  # CC-licensed curated images for Anatomy tab
            'tnm_references': [],
            'anatomy_figures': [],
            'tnm_images': [],
            # Case DICOM Viewer (OneDrive image stacks and annotations)
            'case_image_stacks': [],
            'case_image_annotations': [],
            # TNM Calculator Content (AI-generated calculators and algorithms)
            'tnm_calculator_content': [],
            # Association tables
            'related_cases_links': [],
            'case_calculator_links': [],
            'case_reference_links': [],
            # Audit, analytics & approval
            'case_audit_logs': [],
            'case_view_logs': [],
            'case_approval_queue': [],
            # Spaced repetition
            'user_qa_progress': [],
            # AI cache
            'ai_diagnosis_cache': [],
            'ai_prelim_case_data': [],
            # Clinical Tools
            'clinical_protocols': [],
            'oncall_query_logs': [],
            'reporting_templates': [],
            'incidental_finding_calculators': [],
        }
        
        # Export users (with passwords for sync purposes)
        for user in User.query.all():
            user_data = {
                'id': user.id,  # Include ID for proper mapping
                'email': user.email,
                'password_hash': user.password_hash,
                'full_name': user.full_name,
                'profile_picture': user.profile_picture,  # Cloudinary URL or base64
                'profile_picture_public_id': user.profile_picture_public_id,  # For Cloudinary cleanup
                'public_display_name': user.public_display_name,  # Forum display name
                'role': user.role.value if user.role else 'student',
                'is_active': user.is_active,
                'subscription_status': user.subscription_status.value if user.subscription_status else 'free',
                'payment_status': user.payment_status.value if user.payment_status else 'no_subscription',
                'subscription_start_date': user.subscription_start_date.isoformat() if user.subscription_start_date else None,
                'subscription_end_date': user.subscription_end_date.isoformat() if user.subscription_end_date else None,
                'last_case_viewed': user.last_case_viewed.isoformat() if user.last_case_viewed else None,
                'last_case_viewed_id': user.last_case_viewed_id,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'last_login': user.last_login.isoformat() if user.last_login else None,
            }
            backup_data['users'].append(user_data)
        
        # Export cases
        for case in Case.query.all():
            case_data = {
                'id': case.id,  # Include ID for proper mapping
                'case_number': case.case_number,
                'diagnosis': case.diagnosis,
                'discussion': case.discussion or '',
                'module': case.module.value if case.module else None,
                'body_part': case.body_part.value if case.body_part else None,
                'age_group': case.age_group.value if case.age_group else None,
                'is_public': case.is_public,
                'status': case.status.value if hasattr(case, 'status') and case.status else None,
                'calculator_slug': getattr(case, 'calculator_slug', None),
                'contributor_name': getattr(case, 'contributor_name', None),
                'contributor_notes': getattr(case, 'contributor_notes', None),
                'created_by_user_id': case.created_by_user_id,
                'approved_by_user_id': case.approved_by_user_id if hasattr(case, 'approved_by_user_id') else None,
                'approved_at': case.approved_at.isoformat() if hasattr(case, 'approved_at') and case.approved_at else None,
                'created_at': case.created_at.isoformat() if case.created_at else None,
                'updated_at': case.updated_at.isoformat() if hasattr(case, 'updated_at') and case.updated_at else None,
            }
            
            # Export Questions for this case
            questions = Question.query.filter_by(case_id=case.id).order_by(Question.question_number).all()
            case_data['questions'] = [{
                'question_number': q.question_number,
                'question_text': q.question_text,
            } for q in questions]
            
            # Export Answers for this case
            answers = Answer.query.filter_by(case_id=case.id).order_by(Answer.answer_number).all()
            case_data['answers'] = [{
                'answer_number': a.answer_number,
                'answer_text': a.answer_text,
            } for a in answers]
            
            # Export Images for this case (support both binary and Cloudinary)
            images = CaseImage.query.filter_by(case_id=case.id).all()
            import base64
            case_data['images'] = [{
                'filename': img.image_filename or '',
                'image_type': img.image_type or '',
                'description': img.image_description or '',
                'image_data': base64.b64encode(img.image_data).decode('utf-8') if img.image_data else None,
                # Cloudinary fields (new)
                'image_url': img.image_url,
                'image_public_id': img.image_public_id,
                'image_thumbnail_url': img.image_thumbnail_url,
            } for img in images]
            
            backup_data['cases'].append(case_data)
        
        # Export revision sessions
        for rev_session in RevisionSession.query.all():
            backup_data['revision_sessions'].append({
                'user_id': rev_session.user_id,
                'case_ids': rev_session.get_case_ids_list() if hasattr(rev_session, 'get_case_ids_list') else json.loads(rev_session.case_ids or '[]'),
                'current_case_index': rev_session.current_case_index,
                'created_at': rev_session.created_at.isoformat() if rev_session.created_at else None,
            })
        
        # Export case flags
        for flag in CaseFlag.query.all():
            backup_data['case_flags'].append({
                'user_id': flag.user_id,
                'case_id': flag.case_id,
                'created_at': flag.created_at.isoformat() if flag.created_at else None,
            })
        
        # Export highlights
        for highlight in TextHighlight.query.all():
            backup_data['highlights'].append({
                'user_id': highlight.user_id,
                'case_id': highlight.case_id,
                'text_content': highlight.text_content or '',
                'highlight_color': highlight.highlight_color or 'yellow',
                'field_name': highlight.field_name or 'discussion',
                'created_at': highlight.created_at.isoformat() if highlight.created_at else None,
            })
        
        # Export notes
        for note in CandidateNote.query.all():
            backup_data['notes'].append({
                'user_id': note.user_id,
                'case_id': note.case_id,
                'note_text': note.note_text or '',
                'created_at': note.created_at.isoformat() if note.created_at else None,
                'updated_at': note.updated_at.isoformat() if note.updated_at else None,
            })
        
        # Export revision history (user progress tracking)
        for history in RevisionHistory.query.all():
            backup_data['revision_history'].append({
                'user_id': history.user_id,
                'case_id': history.case_id,
                'module': history.module.value if history.module else None,
                'first_seen_at': history.first_seen_at.isoformat() if history.first_seen_at else None,
                'last_seen_at': history.last_seen_at.isoformat() if history.last_seen_at else None,
                'times_seen': history.times_seen or 0,
                'revision_session_id': history.revision_session_id,
            })
        
        # Export forum messages
        for msg in ForumMessage.query.filter_by(is_deleted=False).all():
            backup_data['forum_messages'].append({
                'id': msg.id,
                'case_id': msg.case_id,
                'user_id': msg.user_id,
                'content': msg.content or '',
                'vote_score': msg.vote_score or 0,
                'is_pinned': msg.is_pinned or False,
                'flag_count': msg.flag_count or 0,
                'image_url': msg.image_url,
                'image_public_id': msg.image_public_id,
                'image_thumbnail_url': msg.image_thumbnail_url,
                'created_at': msg.created_at.isoformat() if msg.created_at else None,
                'updated_at': msg.updated_at.isoformat() if msg.updated_at else None,
            })
        
        # Export forum votes
        for vote in ForumMessageVote.query.all():
            backup_data['forum_votes'].append({
                'message_id': vote.message_id,
                'user_id': vote.user_id,
                'vote_value': vote.vote_value,
                'created_at': vote.created_at.isoformat() if vote.created_at else None,
            })
        
        # Export forum flags (unresolved only)
        for flag in ForumMessageFlag.query.filter_by(is_resolved=False).all():
            backup_data['forum_flags'].append({
                'message_id': flag.message_id,
                'user_id': flag.user_id,
                'reason': flag.reason,
                'details': flag.details,
                'created_at': flag.created_at.isoformat() if flag.created_at else None,
            })
        
        # ==================== AJCC TNM DATA ====================
        
        # Export AJCC Body Sections
        for section in AJCCBodySection.query.order_by(AJCCBodySection.display_order).all():
            backup_data['ajcc_body_sections'].append({
                'id': section.id,
                'section_name': section.section_name,
                'slug': section.slug,
                'display_order': section.display_order,
                'created_at': section.created_at.isoformat() if section.created_at else None,
                'updated_at': section.updated_at.isoformat() if section.updated_at else None,
            })
        
        # Export AJCC Disease Sites
        for disease in AJCCDiseaseSite.query.all():
            backup_data['ajcc_disease_sites'].append({
                'id': disease.id,
                'body_section_id': disease.body_section_id,
                'disease_name': disease.disease_name,
                'slug': disease.slug,
                'ajcc_url_path': disease.ajcc_url_path,
                'display_order': getattr(disease, 'display_order', 0) or 0,
                'frcr_module': getattr(disease, 'frcr_module', None),
                'frcr_body_part': getattr(disease, 'frcr_body_part', None),
                'frcr_age_group': getattr(disease, 'frcr_age_group', None),
                'created_at': disease.created_at.isoformat() if disease.created_at else None,
                'updated_at': disease.updated_at.isoformat() if disease.updated_at else None,
            })
        
        # Export AJCC Diagnosis Years
        for year in AJCCDiagnosisYear.query.all():
            backup_data['ajcc_diagnosis_years'].append({
                'id': year.id,
                'year': year.year,
                'is_default': year.is_default,
                'created_at': year.created_at.isoformat() if year.created_at else None,
            })
        
        # Export AJCC Staging Data (the extracted TNM content)
        for staging in AJCCStagingData.query.all():
            staging_entry = {
                'id': staging.id,
                'disease_site_id': staging.disease_site_id,
                'diagnosis_year_id': staging.diagnosis_year_id,
                'extracted_at': staging.extracted_at.isoformat() if staging.extracted_at else None,
                'extracted_by_user_id': staging.extracted_by_user_id,
                'last_updated_at': staging.last_updated_at.isoformat() if staging.last_updated_at else None,
                'data_version': staging.data_version,
                # JSON data columns
                'tnm_data_json': staging.tnm_data_json,
                'cancers_staged_json': staging.cancers_staged_json,
                'cancers_not_staged_json': staging.cancers_not_staged_json,
                'summary_changes_json': staging.summary_changes_json,
                'primary_sites_json': staging.primary_sites_json,
                'histopathologic_types_json': staging.histopathologic_types_json,
                'imaging_workup_json': staging.imaging_workup_json,
                'staging_rules_json': staging.staging_rules_json,
                'common_scenarios_json': staging.common_scenarios_json,
                'notes_json': staging.notes_json,
                # HTML section columns
                'section_1_quick_reference_html': staging.section_1_quick_reference_html,
                'section_2_cancers_staged_html': staging.section_2_cancers_staged_html,
                'section_3_cancers_not_staged_html': staging.section_3_cancers_not_staged_html,
                'section_4_summary_changes_html': staging.section_4_summary_changes_html,
                'section_5_primary_site_html': staging.section_5_primary_site_html,
                'section_6_histopathologic_type_html': staging.section_6_histopathologic_type_html,
                'section_7_clinical_staging_workup_html': staging.section_7_clinical_staging_workup_html,
                'section_8_staging_rules_html': staging.section_8_staging_rules_html,
                'section_9_common_scenarios_html': staging.section_9_common_scenarios_html,
                'section_10_explanatory_notes_html': staging.section_10_explanatory_notes_html,
                # Raw HTML content (full page backup)
                'raw_html_content': staging.raw_html_content,
                # Curated admin content
                'curated_quick_reference_html': getattr(staging, 'curated_quick_reference_html', None),
                'curated_explanatory_notes_html': getattr(staging, 'curated_explanatory_notes_html', None),
                'curated_by_user_id': getattr(staging, 'curated_by_user_id', None),
                'curated_at': staging.curated_at.isoformat() if getattr(staging, 'curated_at', None) else None,
            }
            backup_data['ajcc_staging_data'].append(staging_entry)
        
        # Export AJCC Disease Mappings (links to FRCR modules/body parts)
        for mapping in AJCCDiseaseMapping.query.all():
            backup_data['ajcc_disease_mappings'].append({
                'id': mapping.id,
                'disease_site_id': mapping.disease_site_id,
                'frcr_module': mapping.frcr_module.value if mapping.frcr_module else None,
                'body_part': mapping.body_part.value if mapping.body_part else None,
                'notes': mapping.notes,
                'created_at': mapping.created_at.isoformat() if mapping.created_at else None,
                'updated_at': mapping.updated_at.isoformat() if mapping.updated_at else None,
            })
        
        # Export AJCC Staging Time Prefixes
        for prefix in AJCCStagingTimePrefix.query.all():
            backup_data['ajcc_staging_time_prefixes'].append({
                'id': prefix.id,
                'prefix': prefix.prefix,
                'name': prefix.name,
                'description': prefix.description,
                'display_order': prefix.display_order,
                'created_at': prefix.created_at.isoformat() if prefix.created_at else None,
            })
        
        # Export Intelligent TNM Data (AI-generated, human-verified)
        for intel in IntelligentTNMData.query.all():
            backup_data['intelligent_tnm_data'].append({
                'id': intel.id,
                'disease_site_id': intel.disease_site_id,
                'diagnosis_year_id': intel.diagnosis_year_id,
                'tnm_memory_aid_t': intel.tnm_memory_aid_t,
                'tnm_memory_aid_n': intel.tnm_memory_aid_n,
                'tnm_memory_aid_m': intel.tnm_memory_aid_m,
                'radiologist_key_points_json': intel.radiologist_key_points_json,
                'upstaging_triggers_json': intel.upstaging_triggers_json,
                'mdt_critical_findings_json': intel.mdt_critical_findings_json,
                'copy_blocks_json': intel.copy_blocks_json,
                'imaging_checklist_json': intel.imaging_checklist_json,
                'reference_images_json': intel.reference_images_json,
                'warnings_json': intel.warnings_json,
                'verified_by_user_id': intel.verified_by_user_id,
                'source_case_id': intel.source_case_id,
                'version': intel.version,
                'created_at': intel.created_at.isoformat() if intel.created_at else None,
                'updated_at': intel.updated_at.isoformat() if intel.updated_at else None,
            })
        
        # Export Case References
        for ref in CaseReference.query.all():
            backup_data['case_references'].append({
                'id': ref.id,
                'case_id': ref.case_id,
                'ref_number': ref.ref_number,
                'title': ref.title,
                'url': ref.url,
                'journal': ref.journal,
                'year': ref.year,
                'is_inline': ref.is_inline,
                'created_at': ref.created_at.isoformat() if ref.created_at else None,
            })
        
        # Export Case Reference Images (CC-licensed curated images for Anatomy tab)
        for img in CaseReferenceImage.query.order_by(CaseReferenceImage.case_id, CaseReferenceImage.display_order).all():
            backup_data['case_reference_images'].append({
                'id': img.id,
                'case_id': img.case_id,
                'source_url': img.source_url,
                'source_domain': img.source_domain,
                'thumbnail_url': img.thumbnail_url,
                'image_type': img.image_type,
                'modality': img.modality,
                'ai_description': img.ai_description,
                'ai_relevance_score': img.ai_relevance_score,
                'admin_note': img.admin_note,
                'display_order': img.display_order,
                'added_by_user_id': img.added_by_user_id,
                'created_at': img.created_at.isoformat() if img.created_at else None,
                'license': img.license,
                'attribution': img.attribution,
            })
        
        # Export TNM References
        for ref in TnmReference.query.all():
            backup_data['tnm_references'].append({
                'id': ref.id,
                'disease_site_id': ref.disease_site_id,
                'ref_number': ref.ref_number,
                'title': ref.title,
                'url': ref.url,
                'journal': ref.journal,
                'year': ref.year,
                'is_inline': ref.is_inline,
                'created_at': ref.created_at.isoformat() if ref.created_at else None,
            })
        
        # Export Anatomy Figures
        for fig in AnatomyFigure.query.all():
            backup_data['anatomy_figures'].append({
                'id': fig.id,
                'figure_id': fig.figure_id,
                'title': fig.title,
                'description': fig.description,
                'source': fig.source,
                'body_region': fig.body_region,
                'figure_type': fig.figure_type,
                'keywords': fig.keywords,
                'modality': fig.modality,
                'cancer_type': fig.cancer_type,
                'staging_category': fig.staging_category,
                'original_url': fig.original_url,
                'cloudinary_url': fig.cloudinary_url,
                'cloudinary_public_id': fig.cloudinary_public_id,
                'thumbnail_url': fig.thumbnail_url,
                'license': fig.license,
                'attribution': fig.attribution,
                'chapter': fig.chapter,
                'page_number': fig.page_number,
                'is_active': fig.is_active,
                'created_at': fig.created_at.isoformat() if fig.created_at else None,
                'updated_at': fig.updated_at.isoformat() if fig.updated_at else None,
            })
        
        # Export TNM Images
        for img in TNMImage.query.all():
            backup_data['tnm_images'].append({
                'id': img.id,
                'disease_site_id': img.disease_site_id,
                'diagnosis_year_id': img.diagnosis_year_id,
                'title': img.title,
                'description': img.description,
                'alt_text': img.alt_text,
                'cloudinary_url': img.cloudinary_url,
                'cloudinary_public_id': img.cloudinary_public_id,
                'width': img.width,
                'height': img.height,
                'image_type': img.image_type,
                'uploaded_by_user_id': img.uploaded_by_user_id,
                'is_active': img.is_active,
                'created_at': img.created_at.isoformat() if img.created_at else None,
                'updated_at': img.updated_at.isoformat() if img.updated_at else None,
            })
        
        # Export Case Image Stacks (R2 + legacy OneDrive)
        for stack in CaseImageStack.query.order_by(CaseImageStack.display_order, CaseImageStack.id).all():
            backup_data['case_image_stacks'].append({
                'id': stack.id,
                'case_id': stack.case_id,
                'study_label': getattr(stack, 'study_label', None),
                'onedrive_share_id': stack.onedrive_share_id,
                'onedrive_folder_path': stack.onedrive_folder_path,
                'config_json': stack.config_json,
                'storage_backend': getattr(stack, 'storage_backend', None),
                'r2_config_json': getattr(stack, 'r2_config_json', None),
                'display_order': getattr(stack, 'display_order', 0),
                'onedrive_refresh_token_encrypted': getattr(stack, 'onedrive_refresh_token_encrypted', None),
                'description_html': getattr(stack, 'description_html', None),
                'created_by_user_id': stack.created_by_user_id,
                'created_at': stack.created_at.isoformat() if stack.created_at else None,
            })
        
        # Export Case Image Annotations (Cornerstone.js annotations; per-study via stack_id)
        for ann in CaseImageAnnotation.query.all():
            backup_data['case_image_annotations'].append({
                'id': ann.id,
                'case_id': ann.case_id,
                'stack_id': getattr(ann, 'stack_id', None),
                'annotations_json': ann.annotations_json,
                'created_by_user_id': ann.created_by_user_id,
                'created_at': ann.created_at.isoformat() if ann.created_at else None,
                'updated_at': ann.updated_at.isoformat() if ann.updated_at else None,
            })

        # Export TNM Calculator Content (AI-generated calculators and algorithms)
        for content in TNMCalculatorContent.query.all():
            backup_data['tnm_calculator_content'].append({
                'id': content.id,
                'slug': content.slug,
                'cancer_name': content.cancer_name,
                'body_section': content.body_section,
                'calculator_html': content.calculator_html,
                'algorithm_discussion_html': content.algorithm_discussion_html,
                'staging_system': content.staging_system,
                'special_features': content.special_features,
                'description': content.description,
                'is_available': content.is_available,
                'generation_prompt': content.generation_prompt,
                'generation_model': content.generation_model,
                'generated_at': content.generated_at.isoformat() if content.generated_at else None,
                'algorithm_case_id': content.algorithm_case_id,
                'created_by_user_id': content.created_by_user_id,
                'created_at': content.created_at.isoformat() if content.created_at else None,
                'updated_at': content.updated_at.isoformat() if content.updated_at else None,
            })

        # Export Related Cases (association table)
        for row in db.session.execute(related_cases.select()).fetchall():
            backup_data['related_cases_links'].append({
                'case_id': row.case_id,
                'related_case_id': row.related_case_id,
                'relation_type': row.relation_type if hasattr(row, 'relation_type') else 'related',
            })

        # Export Case-Calculator Links (association table)
        for row in db.session.execute(case_calculator_links.select()).fetchall():
            backup_data['case_calculator_links'].append({
                'case_id': row.case_id,
                'calculator_id': row.calculator_id,
                'created_by_user_id': row.created_by_user_id,
            })

        # Export Case-Reference Links (association table)
        for row in db.session.execute(case_reference_links.select()).fetchall():
            backup_data['case_reference_links'].append({
                'case_id': row.case_id,
                'reference_id': row.reference_id,
                'created_by_user_id': row.created_by_user_id,
            })

        # Export Case Audit Logs
        for log in CaseAuditLog.query.order_by(CaseAuditLog.id).all():
            backup_data['case_audit_logs'].append({
                'id': log.id,
                'case_id': log.case_id,
                'user_id': log.user_id,
                'action': log.action,
                'changes': log.changes,
                'notes': log.notes,
                'created_at': log.created_at.isoformat() if log.created_at else None,
            })

        # Export Case View Logs
        for vlog in CaseViewLog.query.order_by(CaseViewLog.id).all():
            backup_data['case_view_logs'].append({
                'user_id': vlog.user_id,
                'case_id': vlog.case_id,
                'viewed_at': vlog.viewed_at.isoformat() if vlog.viewed_at else None,
                'time_spent_seconds': vlog.time_spent_seconds,
            })

        # Export Case Approval Queue
        for entry in CaseApprovalQueue.query.all():
            backup_data['case_approval_queue'].append({
                'case_id': entry.case_id,
                'submitted_by_user_id': entry.submitted_by_user_id,
                'submitted_at': entry.submitted_at.isoformat() if entry.submitted_at else None,
                'admin_notes': entry.admin_notes,
            })

        # Export User QA Progress (spaced repetition state)
        for prog in UserQAProgress.query.all():
            backup_data['user_qa_progress'].append({
                'user_id': prog.user_id,
                'question_id': prog.question_id,
                'case_id': prog.case_id,
                'ease_factor': prog.ease_factor,
                'interval_days': prog.interval_days,
                'repetition_number': prog.repetition_number,
                'next_review_date': prog.next_review_date.isoformat() if prog.next_review_date else None,
                'last_reviewed_at': prog.last_reviewed_at.isoformat() if prog.last_reviewed_at else None,
                'times_correct': prog.times_correct,
                'times_incorrect': prog.times_incorrect,
                'created_at': prog.created_at.isoformat() if prog.created_at else None,
            })

        # Export AI Diagnosis Cache
        for cache in AiDiagnosisCache.query.all():
            backup_data['ai_diagnosis_cache'].append({
                'id': cache.id,
                'diagnosis': cache.diagnosis,
                'provider': cache.provider,
                'model_name': cache.model_name,
                'first_case_id': cache.first_case_id,
                'first_user_id': cache.first_user_id,
                'first_generated_at': cache.first_generated_at.isoformat() if cache.first_generated_at else None,
                'query_count': cache.query_count,
                'last_queried_at': cache.last_queried_at.isoformat() if cache.last_queried_at else None,
            })

        # Export AI Prelim Case Data (audit trail for AI-generated cases)
        for apcd in AiPrelimCaseData.query.all():
            backup_data['ai_prelim_case_data'].append({
                'id': apcd.id,
                'case_id': apcd.case_id,
                'created_by_user_id': apcd.created_by_user_id,
                'provider': apcd.provider,
                'model_name': apcd.model_name,
                'prompt_version': apcd.prompt_version,
                'request_payload': apcd.request_payload,
                'response_payload': apcd.response_payload,
                'created_at': apcd.created_at.isoformat() if apcd.created_at else None,
            })

        # Export Clinical Protocols (On-Call Helper knowledge base)
        for protocol in ClinicalProtocol.query.all():
            backup_data['clinical_protocols'].append({
                'id': protocol.id,
                'category': protocol.category,
                'title': protocol.title,
                'keywords': protocol.keywords,
                'content_structured': protocol.content_structured,
                'content_html': protocol.content_html,
                'source_citation': protocol.source_citation,
                'guideline_version': protocol.guideline_version,
                'source_url': protocol.source_url,
                'is_published': protocol.is_published,
                'verified_by_user_id': protocol.verified_by_user_id,
                'verified_at': protocol.verified_at.isoformat() if protocol.verified_at else None,
                'created_by_user_id': protocol.created_by_user_id,
                'created_at': protocol.created_at.isoformat() if protocol.created_at else None,
                'updated_at': protocol.updated_at.isoformat() if protocol.updated_at else None,
            })

        # Export On-Call Query Logs (audit trail)
        for log in OnCallQueryLog.query.all():
            backup_data['oncall_query_logs'].append({
                'id': log.id,
                'user_id': log.user_id,
                'query_text': log.query_text,
                'matched_protocol_ids': log.matched_protocol_ids,
                'ai_response_text': log.ai_response_text,
                'model_used': log.model_used,
                'token_count': log.token_count,
                'response_source': log.response_source,
                'created_at': log.created_at.isoformat() if log.created_at else None,
            })

        # Export Reporting Templates (admin-curated + AI-generated cached algorithms)
        for rt in ReportingTemplate.query.all():
            backup_data['reporting_templates'].append({
                'id': rt.id,
                'slug': rt.slug,
                'title': rt.title,
                'category': rt.category,
                'body_section': rt.body_section,
                'description': rt.description,
                'keywords': rt.keywords,
                'template_html': rt.template_html,
                'algorithm_html': rt.algorithm_html,
                'source_citation': rt.source_citation,
                'guideline_version': rt.guideline_version,
                'is_available': rt.is_available,
                'is_ai_generated': rt.is_ai_generated,
                'verified_by_user_id': rt.verified_by_user_id,
                'verified_at': rt.verified_at.isoformat() if rt.verified_at else None,
                'pacs_report_text': rt.pacs_report_text,
                'generation_prompt': rt.generation_prompt,
                'generation_model': rt.generation_model,
                'generated_at': rt.generated_at.isoformat() if rt.generated_at else None,
                'created_by_user_id': rt.created_by_user_id,
                'last_edit_note': rt.last_edit_note,
                'created_at': rt.created_at.isoformat() if rt.created_at else None,
                'updated_at': rt.updated_at.isoformat() if rt.updated_at else None,
            })

        # Export Incidental Finding Calculators
        for ifc in IncidentalFindingCalculator.query.all():
            backup_data['incidental_finding_calculators'].append({
                'id': ifc.id,
                'slug': ifc.slug,
                'finding_name': ifc.finding_name,
                'body_section': ifc.body_section,
                'category': ifc.category,
                'description': ifc.description,
                'keywords': ifc.keywords,
                'calculator_html': ifc.calculator_html,
                'algorithm_html': ifc.algorithm_html,
                'guideline_source': ifc.guideline_source,
                'guideline_version': ifc.guideline_version,
                'guideline_url': ifc.guideline_url,
                'is_available': ifc.is_available,
                'generation_prompt': ifc.generation_prompt,
                'generation_model': ifc.generation_model,
                'generated_at': ifc.generated_at.isoformat() if ifc.generated_at else None,
                'verified_by_user_id': ifc.verified_by_user_id,
                'verified_at': ifc.verified_at.isoformat() if ifc.verified_at else None,
                'created_by_user_id': ifc.created_by_user_id,
                'last_edit_note': ifc.last_edit_note,
                'created_at': ifc.created_at.isoformat() if ifc.created_at else None,
                'updated_at': ifc.updated_at.isoformat() if ifc.updated_at else None,
            })

        # Create JSON file in memory
        json_data = json.dumps(backup_data, indent=2)
        json_bytes = io.BytesIO(json_data.encode('utf-8'))
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'radinsights_backup_{timestamp}.json'
        
        # Update session with last backup time
        session['last_backup_time'] = datetime.utcnow().isoformat()
        
        return send_file(
            json_bytes,
            mimetype='application/json',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({'error': f'Backup failed: {str(e)}'}), 500


@backup_bp.route('/restore', methods=['POST'])
@login_required
def restore_backup():
    """Restore database from uploaded JSON backup with smart merge"""
    if not check_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    if 'backup_file' not in request.files:
        return jsonify({'error': 'No backup file provided'}), 400
    
    file = request.files['backup_file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith('.json'):
        return jsonify({'error': 'Only JSON backup files are supported'}), 400
    
    # FRESH APPROACH: Handle large files (26MB+) by processing in chunks
    # Vercel has a 4.5MB limit, but we can work around it by processing the file stream
    try:
        # Get file size (seek to end, get position, then reset)
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        print(f"[IMPORT] Backup file size: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)")
        
        # For very large files, we need to process them differently
        # Read the file content - Flask's file object handles streaming
        # Read in chunks to avoid memory issues
        file_content_parts = []
        chunk_size = 1024 * 1024  # 1MB chunks
        total_read = 0
        
        while True:
            chunk = file.read(chunk_size)
            if not chunk:
                break
            file_content_parts.append(chunk)
            total_read += len(chunk)
            print(f"[IMPORT] Read chunk: {total_read / 1024 / 1024:.2f} MB / {file_size / 1024 / 1024:.2f} MB")
        
        # Combine chunks and decode
        file_content = b''.join(file_content_parts).decode('utf-8')
        
        # Clear references to free memory
        file = None
        file_content_parts = None
        
        print(f"[IMPORT] Successfully read {len(file_content)} characters from backup file ({file_size / 1024 / 1024:.2f} MB)")
        
        # Handle case where file might already be a string (double-encoded)
        if isinstance(file_content, str):
            try:
                backup_data = json.loads(file_content)
            except json.JSONDecodeError:
                # If it's already a dict (shouldn't happen but handle it)
                backup_data = file_content if isinstance(file_content, dict) else json.loads(file_content)
        else:
            backup_data = file_content
        
        # Clear file_content from memory after parsing (for large files)
        # Keep backup_data as it's needed for the import
        file_content = None
        
        # Ensure backup_data is a dictionary
        if not isinstance(backup_data, dict):
            return jsonify({'error': f'Invalid backup file format: expected dict, got {type(backup_data).__name__}'}), 400
        
        # Validate backup structure
        if 'metadata' not in backup_data:
            return jsonify({'error': 'Invalid backup file format: missing metadata'}), 400
        
        # Detect source system (FRCR Examiner vs FRCR Revision)
        metadata = backup_data.get('metadata', {})
        app_name = metadata.get('app_name', '').upper()
        is_frcr_examiner = 'EXAMINER' in app_name or metadata.get('source_system') == 'frcr_examiner'
        is_frcr_revision = 'REVISION' in app_name or metadata.get('app_name') == 'FRCR_REVISION' or metadata.get('app_name') == 'RadInsights'
        
        # Default to FRCR Examiner if cannot determine (for backward compatibility)
        if not is_frcr_examiner and not is_frcr_revision:
            # Check if backup has FRCR Examiner structure (separate case_images array)
            if 'case_images' in backup_data and isinstance(backup_data.get('case_images'), list):
                is_frcr_examiner = True
            else:
                is_frcr_revision = True
        
        print(f"[IMPORT] Detected backup source: {'FRCR_EXAMINER' if is_frcr_examiner else 'FRCR_REVISION'}")
        
        # Check if user confirmed overwrite for existing data
        # Support both form data and JSON data
        if request.is_json:
            json_data = request.get_json() or {}
            overwrite_existing = json_data.get('overwrite_existing') == True or json_data.get('overwrite_existing') == 'true'
            confirm_overwrite = json_data.get('confirm_overwrite') == True or json_data.get('confirm_overwrite') == 'true'
        else:
            overwrite_existing = request.form.get('overwrite_existing') == 'true'
            confirm_overwrite = request.form.get('confirm_overwrite') == 'true'
        
        if not confirm_overwrite:
            return jsonify({'error': 'Please confirm data import'}), 400
        
        stats = {
            'users': {'added': 0, 'updated': 0, 'skipped': 0},
            'cases': {'added': 0, 'updated': 0, 'skipped': 0},
            'staging': {'added': 0, 'images_stored': 0},  # Cases sent to staging for review, and images stored in them
            'questions': {'added': 0},
            'answers': {'added': 0},
            'images': {'added': 0},
            'revision_sessions': {'added': 0, 'skipped': 0},
            'case_flags': {'added': 0, 'skipped': 0},
            'highlights': {'added': 0},
            'notes': {'added': 0},
        }
        
        # Generate import batch ID for staging cases
        import_batch_id = f"backup_import_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
        
        # Get valid field names for each model
        valid_user_fields = get_model_fields(User)
        valid_case_fields = get_model_fields(Case)
        
        # Import Users
        # For FRCR Examiner: Skip user import, all cases will be mapped to current_user
        # For FRCR Revision: Import users normally
        user_id_map = {}  # Map old user IDs from backup to new user IDs
        
        if is_frcr_examiner:
            # FRCR Examiner: Don't import users, map everything to current_user
            print(f"[IMPORT] FRCR Examiner backup: Skipping user import, mapping all cases to current user {current_user.id}")
            # Create a dummy mapping for any user references (they'll be replaced with current_user.id)
            users_list = backup_data.get('users', [])
            if isinstance(users_list, list):
                for user_data in users_list:
                    old_id = user_data.get('id') if isinstance(user_data, dict) else None
                    if old_id:
                        user_id_map[old_id] = current_user.id
        else:
            # FRCR Revision: Import users normally
            users_list = backup_data.get('users', [])
            if not isinstance(users_list, list):
                return jsonify({'error': 'Invalid backup format: users must be a list'}), 400
            
            for user_data in users_list:
                # Ensure user_data is a dictionary
                if not isinstance(user_data, dict):
                    print(f"[IMPORT] Warning: Skipping invalid user data (not a dict): {type(user_data).__name__}")
                    continue
                
                # Filter out unknown fields
                filtered_data = {k: v for k, v in user_data.items() if k in valid_user_fields or k in ['email', 'password_hash', 'full_name', 'role', 'is_active', 'subscription_status', 'payment_status']}
                
                existing_user = User.query.filter_by(email=user_data.get('email')).first()
                
                if existing_user:
                    if overwrite_existing:
                        # Update existing user - datetime and enum fields need special handling for SQLite
                        USER_DATETIME_KEYS = [
                            'created_at', 'last_login', 'subscription_start_date', 'subscription_end_date',
                            'deleted_at', 'last_case_viewed', 'notion_connected_at', 'anki_connected_at',
                            'sciencedirect_connected_at', 'recovery_token_expires'
                        ]
                        for key, value in filtered_data.items():
                            if key in ('email', 'id'):
                                continue
                            if key == 'role' and value:
                                try:
                                    existing_user.role = UserRole(value)
                                except (ValueError, KeyError) as e:
                                    print(f"[IMPORT] Warning: Could not set user role to {value}: {e}")
                            elif key == 'subscription_status' and value:
                                try:
                                    existing_user.subscription_status = SubscriptionStatus(value)
                                except (ValueError, KeyError) as e:
                                    print(f"[IMPORT] Warning: Could not set subscription_status to {value}: {e}")
                            elif key == 'payment_status' and value:
                                try:
                                    existing_user.payment_status = PaymentStatus(value)
                                except (ValueError, KeyError) as e:
                                    print(f"[IMPORT] Warning: Could not set payment_status to {value}: {e}")
                            elif key in USER_DATETIME_KEYS and value is not None:
                                parsed = _parse_datetime_for_sqlite(value)
                                if parsed is not None and hasattr(existing_user, key):
                                    setattr(existing_user, key, parsed)
                            elif hasattr(existing_user, key) and key not in USER_DATETIME_KEYS:
                                # Skip enum-like fields that might be empty string
                                if key in ('subscription_status', 'payment_status') and not value:
                                    continue
                                setattr(existing_user, key, value)
                        stats['users']['updated'] += 1
                    else:
                        stats['users']['skipped'] += 1
                else:
                    # Create new user
                    try:
                        role_value = filtered_data.get('role', 'student')
                        user_role = UserRole(role_value) if role_value else UserRole.STUDENT
                    except (ValueError, KeyError) as e:
                        print(f"[IMPORT] Warning: Could not set user role to {filtered_data.get('role')}, defaulting to student: {e}")
                        user_role = UserRole.STUDENT
                    
                    user = User(
                        email=filtered_data.get('email'),
                        password_hash=filtered_data.get('password_hash', ''),
                        full_name=filtered_data.get('full_name', ''),
                        role=user_role,
                        is_active=filtered_data.get('is_active', True),
                    )
                    # Set profile and display fields
                    if user_data.get('profile_picture'):
                        user.profile_picture = user_data['profile_picture']
                    if user_data.get('profile_picture_public_id'):
                        user.profile_picture_public_id = user_data['profile_picture_public_id']
                    if user_data.get('public_display_name'):
                        user.public_display_name = user_data['public_display_name']
                    parsed_lcv = _parse_datetime_for_sqlite(user_data.get('last_case_viewed'))
                    if parsed_lcv is not None:
                        user.last_case_viewed = parsed_lcv
                    if user_data.get('last_case_viewed_id'):
                        user.last_case_viewed_id = user_data['last_case_viewed_id']
                    
                    if filtered_data.get('subscription_status'):
                        try:
                            user.subscription_status = SubscriptionStatus(filtered_data['subscription_status'])
                        except (ValueError, KeyError) as e:
                            print(f"[IMPORT] Warning: Could not set subscription_status to {filtered_data.get('subscription_status')}: {e}")
                    if filtered_data.get('payment_status'):
                        try:
                            user.payment_status = PaymentStatus(filtered_data['payment_status'])
                        except (ValueError, KeyError) as e:
                            print(f"[IMPORT] Warning: Could not set payment_status to {filtered_data.get('payment_status')}: {e}")
                    parsed_sd = _parse_datetime_for_sqlite(user_data.get('subscription_start_date'))
                    if parsed_sd is not None:
                        user.subscription_start_date = parsed_sd
                    parsed_ed = _parse_datetime_for_sqlite(user_data.get('subscription_end_date'))
                    if parsed_ed is not None:
                        user.subscription_end_date = parsed_ed
                    parsed_ca = _parse_datetime_for_sqlite(filtered_data.get('created_at'))
                    if parsed_ca is not None:
                        user.created_at = parsed_ca
                    parsed_ll = _parse_datetime_for_sqlite(user_data.get('last_login'))
                    if parsed_ll is not None:
                        user.last_login = parsed_ll
                    db.session.add(user)
                    stats['users']['added'] += 1
            
            try:
                db.session.commit()
            except Exception as commit_error:
                db.session.rollback()
                print(f"[IMPORT] ERROR during user commit: {commit_error}")
                import traceback
                traceback.print_exc()
                raise
            
            # Build user email to ID mapping and old ID to new ID mapping
            user_email_map = {u.email: u.id for u in User.query.all()}
            
            # Build ID mapping for users (old backup ID -> new database ID)
            for user_data in backup_data.get('users', []):
                if not isinstance(user_data, dict):
                    continue
                old_id = user_data.get('id')
                email = user_data.get('email')
                if old_id and email:
                    new_user = User.query.filter_by(email=email).first()
                    if new_user:
                        user_id_map[old_id] = new_user.id
        
        # Import Cases with batch commits (every 50 cases)
        case_id_map = {}  # Map old case IDs from backup to new case IDs (production cases only)
        staging_id_map = {}  # Map old case IDs from backup to staging IDs (staging cases only)
        
        CASE_BATCH_SIZE = 50  # Commit every 50 cases to avoid long transactions
        cases_list = backup_data.get('cases', [])
        
        for case_idx, case_data in enumerate(cases_list):
            # Filter out unknown fields - only keep fields that exist in Case model
            valid_case_keys = ['case_number', 'diagnosis', 'discussion', 'module', 'body_part', 'age_group', 'is_public', 'calculator_slug', 'contributor_name', 'contributor_notes', 'status', 'created_by_user_id', 'approved_by_user_id', 'approved_at', 'created_at', 'updated_at']
            filtered_data = {k: v for k, v in case_data.items() if k in valid_case_keys}
            
            old_case_id = case_data.get('id')  # Store old ID for mapping
            
            # Find existing case by case_number (or create new)
            case_number = filtered_data.get('case_number')
            existing_case = Case.query.filter_by(case_number=case_number).first() if case_number else None
            
            if existing_case:
                if overwrite_existing:
                    # Update existing case
                    for key, value in filtered_data.items():
                        if key == 'status' and value:
                            try:
                                existing_case.status = CaseStatus(str(value).strip())
                            except (ValueError, KeyError) as e:
                                print(f"[IMPORT] Warning: Could not set status to '{value}': {e}")
                        elif key in ['module', 'body_part', 'age_group'] and value:
                            try:
                                # Convert to string and strip whitespace
                                enum_value_str = str(value).strip() if value is not None else None
                                if not enum_value_str:
                                    continue
                                    
                                if key == 'module':
                                    # Try by value first (export format), then by name
                                    try:
                                        existing_case.module = FRCRModule(enum_value_str)
                                    except (ValueError, KeyError):
                                        try:
                                            existing_case.module = FRCRModule[enum_value_str]
                                        except (ValueError, KeyError) as e:
                                            print(f"[IMPORT] Warning: Could not set module to '{enum_value_str}' (type: {type(value).__name__}): {e}")
                                elif key == 'body_part':
                                    try:
                                        existing_case.body_part = BodyPart(enum_value_str)
                                    except (ValueError, KeyError):
                                        try:
                                            existing_case.body_part = BodyPart[enum_value_str]
                                        except (ValueError, KeyError) as e:
                                            print(f"[IMPORT] Warning: Could not set body_part to '{enum_value_str}' (type: {type(value).__name__}): {e}")
                                elif key == 'age_group':
                                    try:
                                        existing_case.age_group = AgeGroup(enum_value_str)
                                    except (ValueError, KeyError):
                                        try:
                                            existing_case.age_group = AgeGroup[enum_value_str]
                                        except (ValueError, KeyError) as e:
                                            print(f"[IMPORT] Warning: Could not set age_group to '{enum_value_str}' (type: {type(value).__name__}): {e}")
                            except Exception as e:
                                print(f"[IMPORT] Warning: Could not set {key} to {value} (type: {type(value).__name__}): {e}")
                                pass
                        elif key == 'created_at' and value:
                            # Convert ISO string to datetime object for SQLite compatibility
                            try:
                                if isinstance(value, str):
                                    existing_case.created_at = datetime.fromisoformat(value)
                                elif isinstance(value, datetime):
                                    existing_case.created_at = value
                            except (ValueError, TypeError) as e:
                                print(f"[IMPORT] Warning: Could not parse case created_at datetime: {value}, error: {e}")
                                pass
                        elif key not in ['id', 'case_number'] and hasattr(existing_case, key):
                            setattr(existing_case, key, value)
                    
                    # Update Q&A if overwriting
                    if overwrite_existing:
                        # Delete existing Q&A
                        Question.query.filter_by(case_id=existing_case.id).delete()
                        Answer.query.filter_by(case_id=existing_case.id).delete()
                        # Add new Q&A
                        questions_list = case_data.get('questions', [])
                        if isinstance(questions_list, list):
                            for q_data in questions_list:
                                if not isinstance(q_data, dict):
                                    print(f"[IMPORT] Warning: Skipping invalid question data (not a dict)")
                                    continue
                                question = Question(
                                    case_id=existing_case.id,
                                    question_number=q_data.get('question_number', 0),
                                    question_text=q_data.get('question_text', ''),
                            )
                            db.session.add(question)
                            stats['questions']['added'] += 1
                        
                        answers_list = case_data.get('answers', [])
                        if isinstance(answers_list, list):
                            for a_data in answers_list:
                                if not isinstance(a_data, dict):
                                    print(f"[IMPORT] Warning: Skipping invalid answer data (not a dict)")
                                    continue
                                answer = Answer(
                                    case_id=existing_case.id,
                                    answer_number=a_data.get('answer_number', 0),
                                    answer_text=a_data.get('answer_text', ''),
                                )
                                db.session.add(answer)
                                stats['answers']['added'] += 1
                        
                        # Update images if overwriting
                        CaseImage.query.filter_by(case_id=existing_case.id).delete()
                        import base64
                        images_list = case_data.get('images', [])
                        if isinstance(images_list, list):
                            for img_data in images_list:
                                if not isinstance(img_data, dict):
                                    print(f"[IMPORT] Warning: Skipping invalid image data (not a dict)")
                                    continue
                                image_data_binary = None
                                if img_data.get('image_data'):
                                    try:
                                        image_data_binary = base64.b64decode(img_data['image_data'])
                                    except Exception as e:
                                        print(f"[IMPORT] Warning: Failed to decode image data: {e}")
                                        continue
                                
                                # Support both field name formats: 'image_filename'/'image_description' (FRCR Examiner) and 'filename'/'description' (FRCR Revision)
                                image_filename = img_data.get('image_filename') or img_data.get('filename', '')
                                image_description = img_data.get('image_description') or img_data.get('description', '')
                                image_type = img_data.get('image_type', 'image/jpeg')
                                
                                # Check for Cloudinary URL (preferred) or binary data (legacy)
                                image_url = img_data.get('image_url')
                                image_public_id = img_data.get('image_public_id')
                                image_thumbnail_url = img_data.get('image_thumbnail_url')
                                
                                # Only create image if we have image data OR Cloudinary URL
                                if image_data_binary or image_url:
                                    image = CaseImage(
                                        case_id=existing_case.id,
                                        image_filename=image_filename,
                                        image_type=image_type,
                                        image_description=image_description,
                                        image_data=image_data_binary,
                                        # Cloudinary fields
                                        image_url=image_url,
                                        image_public_id=image_public_id,
                                        image_thumbnail_url=image_thumbnail_url,
                                    )
                                    db.session.add(image)
                                    stats['images']['added'] += 1
                    
                    stats['cases']['updated'] += 1
                    new_case_id = existing_case.id
                else:
                    stats['cases']['skipped'] += 1
                    new_case_id = existing_case.id
            else:
                # Check for missing critical fields
                missing_fields = []
                if not filtered_data.get('module'):
                    missing_fields.append('module')
                if not filtered_data.get('body_part'):
                    missing_fields.append('body_part')
                if not filtered_data.get('age_group'):
                    missing_fields.append('age_group')
                
                # If missing critical fields, send to staging for review
                if missing_fields:
                    # Create staging entry for admin review
                    import base64
                    import json as json_lib
                    
                    # Store Q&A as JSON for staging (legacy format for compatibility)
                    questions_list = case_data.get('questions', [])
                    if not isinstance(questions_list, list):
                        questions_list = []
                    questions_json = json_lib.dumps([{
                        'question_number': q.get('question_number', 0) if isinstance(q, dict) else 0,
                        'question_text': q.get('question_text', '') if isinstance(q, dict) else str(q)
                    } for q in questions_list if isinstance(q, dict)])
                    
                    answers_list = case_data.get('answers', [])
                    if not isinstance(answers_list, list):
                        answers_list = []
                    answers_json = json_lib.dumps([{
                        'answer_number': a.get('answer_number', 0) if isinstance(a, dict) else 0,
                        'answer_text': a.get('answer_text', '') if isinstance(a, dict) else str(a)
                    } for a in answers_list if isinstance(a, dict)])
                    
                    # For FRCR Examiner: Store source system as 'frcr_examiner' to track origin
                    source_system = 'frcr_examiner' if is_frcr_examiner else 'backup_import'
                    
                    staging = ImportedCaseStaging(
                        original_id=old_case_id,
                        case_number=filtered_data.get('case_number'),
                        diagnosis=filtered_data.get('diagnosis', ''),
                        discussion=filtered_data.get('discussion', ''),
                        questions=questions_json,  # Legacy format for staging
                        answers=answers_json,  # Legacy format for staging
                        enrichment_status='pending',
                        import_batch_id=import_batch_id,
                        source_system=source_system,
                        enrichment_notes=f"Missing fields: {', '.join(missing_fields)}. Requires admin review.",
                    )
                    db.session.add(staging)
                    try:
                        db.session.flush()
                    except Exception as flush_error:
                        db.session.rollback()
                        print(f"[IMPORT] ERROR during staging flush: {flush_error}")
                        import traceback
                        traceback.print_exc()
                        raise
                    
                    # Store images temporarily in enrichment_notes (will be migrated on promotion)
                    # Process images from separate case_images array for this staging case
                    import base64
                    import json as json_lib
                    staging_images = []
                    case_number_for_match = filtered_data.get('case_number')
                    
                    # Normalize case_number for comparison (convert to string)
                    case_number_str = str(case_number_for_match) if case_number_for_match is not None else None
                    
                    print(f"[IMPORT] Looking for images for staging case: old_case_id={old_case_id} (type: {type(old_case_id).__name__}), case_number={case_number_for_match} (type: {type(case_number_for_match).__name__})")
                    print(f"[IMPORT] Total images in backup: {len(backup_data.get('case_images', []))}")
                    
                    for img_data in backup_data.get('case_images', []):
                        if not isinstance(img_data, dict):
                            continue
                        
                        # Try to match by case_id first, then by case_number if available
                        img_case_id = img_data.get('case_id')
                        img_case_number = img_data.get('case_number')
                        
                        # Normalize types for comparison
                        # Convert both to same type (prefer int for IDs, string for case_numbers)
                        img_case_id_normalized = int(img_case_id) if img_case_id is not None and str(img_case_id).isdigit() else img_case_id
                        old_case_id_normalized = int(old_case_id) if old_case_id is not None and str(old_case_id).isdigit() else old_case_id
                        
                        img_case_number_str = str(img_case_number) if img_case_number is not None else None
                        
                        # Match if case_id matches OR case_number matches
                        matches = False
                        if old_case_id_normalized is not None and img_case_id_normalized is not None:
                            if img_case_id_normalized == old_case_id_normalized:
                                matches = True
                                print(f"[IMPORT] ✓ Matched image by case_id: {old_case_id_normalized}")
                        elif case_number_str and img_case_number_str:
                            # Try exact match first
                            if img_case_number_str == case_number_str:
                                matches = True
                                print(f"[IMPORT] ✓ Matched image by case_number (exact): {case_number_str}")
                            # Try numeric comparison if both are numeric
                            elif case_number_str.isdigit() and img_case_number_str.isdigit():
                                if int(case_number_str) == int(img_case_number_str):
                                    matches = True
                                    print(f"[IMPORT] ✓ Matched image by case_number (numeric): {case_number_str}")
                        
                        if matches:
                            # This image belongs to this staging case
                            try:
                                image_filename = img_data.get('image_filename') or img_data.get('filename', '')
                                image_description = img_data.get('image_description') or img_data.get('description', '')
                                image_type = img_data.get('image_type', 'image/jpeg')
                                image_data_base64 = img_data.get('image_data')
                                
                                if image_data_base64:
                                    staging_images.append({
                                        'filename': image_filename,
                                        'image_type': image_type,
                                        'description': image_description,
                                        'image_data': image_data_base64  # Keep as base64 string
                                    })
                                    print(f"[IMPORT] Added image to staging: {image_filename} (data length: {len(image_data_base64)})")
                                else:
                                    print(f"[IMPORT] Warning: Image {image_filename} has no image_data")
                            except Exception as img_err:
                                print(f"[IMPORT] Warning: Failed to process image for staging case {old_case_id}: {img_err}")
                                import traceback
                                traceback.print_exc()
                    
                    if not staging_images:
                        print(f"[IMPORT] ⚠️ Warning: No images found for staging case (old_case_id={old_case_id}, case_number={case_number_for_match})")
                        print(f"[IMPORT] Total images in backup: {len(backup_data.get('case_images', []))}")
                        # Debug: show first few image case_ids and case_numbers
                        sample_data = []
                        for img in backup_data.get('case_images', [])[:10]:
                            if isinstance(img, dict):
                                sample_data.append({
                                    'case_id': img.get('case_id'),
                                    'case_number': img.get('case_number'),
                                    'filename': img.get('image_filename') or img.get('filename', 'N/A')
                                })
                        print(f"[IMPORT] Sample image data (first 10): {sample_data}")
                        # Also check if any images have matching case_number
                        matching_by_number = [img for img in backup_data.get('case_images', []) 
                                            if isinstance(img, dict) and 
                                            str(img.get('case_number', '')) == case_number_str]
                        if matching_by_number:
                            print(f"[IMPORT] Found {len(matching_by_number)} images with matching case_number but didn't match - check logic")
                    
                    # Store images JSON in enrichment_notes with special marker
                    if staging_images:
                        images_json_str = json_lib.dumps(staging_images)
                        if staging.enrichment_notes:
                            staging.enrichment_notes = f"[IMAGES_JSON]{images_json_str}[/IMAGES_JSON]\n{staging.enrichment_notes}"
                        else:
                            staging.enrichment_notes = f"[IMAGES_JSON]{images_json_str}[/IMAGES_JSON]"
                        
                        # Explicitly mark the object as modified to ensure SQLAlchemy tracks the change
                        from sqlalchemy.orm.attributes import flag_modified
                        flag_modified(staging, 'enrichment_notes')
                        
                        print(f"[IMPORT] ✓ Stored {len(staging_images)} images in staging case {staging.id} enrichment_notes")
                        print(f"[IMPORT] Enrichment notes length: {len(staging.enrichment_notes)}")
                        print(f"[IMPORT] Enrichment notes preview: {staging.enrichment_notes[:200]}...")
                        stats['staging']['images_stored'] += len(staging_images)
                    else:
                        print(f"[IMPORT] ⚠️ No images to store for staging case {staging.id}")
                    
                    stats['staging']['added'] += 1
                    # Store staging ID mapping (for image processing)
                    if old_case_id:
                        staging_id_map[old_case_id] = staging.id
                    # Don't create case_id_map entry for staging cases (they're not in production yet)
                    continue
                
                # All critical fields present - create case directly
                case = Case(
                    case_number=filtered_data.get('case_number', ''),
                    diagnosis=filtered_data.get('diagnosis', ''),
                    discussion=filtered_data.get('discussion', ''),
                    is_public=filtered_data.get('is_public', True),
                    calculator_slug=filtered_data.get('calculator_slug'),
                    contributor_name=filtered_data.get('contributor_name'),
                    contributor_notes=filtered_data.get('contributor_notes'),
                )
                # Set status if provided
                if filtered_data.get('status'):
                    try:
                        case.status = CaseStatus(filtered_data['status'])
                    except (ValueError, KeyError):
                        pass
                
                # Set enums - try by value first (export format), then by name
                # Validate and convert to string first to avoid pattern matching errors
                if filtered_data.get('module'):
                    module_value = filtered_data['module']
                    if module_value is not None:
                        try:
                            # Convert to string and strip whitespace
                            module_str = str(module_value).strip()
                            if module_str:
                                try:
                                    case.module = FRCRModule(module_str)
                                except (ValueError, KeyError):
                                    try:
                                        case.module = FRCRModule[module_str]
                                    except (ValueError, KeyError) as e:
                                        print(f"[IMPORT] Warning: Could not set module to '{module_str}' (type: {type(module_value).__name__}): {e}")
                                except Exception as e:
                                    print(f"[IMPORT] Warning: Unexpected error setting module to '{module_str}': {e}")
                        except Exception as e:
                            print(f"[IMPORT] Warning: Could not process module value {module_value}: {e}")
                if filtered_data.get('body_part'):
                    body_part_value = filtered_data['body_part']
                    if body_part_value is not None:
                        try:
                            body_part_str = str(body_part_value).strip()
                            if body_part_str:
                                try:
                                    case.body_part = BodyPart(body_part_str)
                                except (ValueError, KeyError):
                                    try:
                                        case.body_part = BodyPart[body_part_str]
                                    except (ValueError, KeyError) as e:
                                        print(f"[IMPORT] Warning: Could not set body_part to '{body_part_str}' (type: {type(body_part_value).__name__}): {e}")
                                except Exception as e:
                                    print(f"[IMPORT] Warning: Unexpected error setting body_part to '{body_part_str}': {e}")
                        except Exception as e:
                            print(f"[IMPORT] Warning: Could not process body_part value {body_part_value}: {e}")
                if filtered_data.get('age_group'):
                    age_group_value = filtered_data['age_group']
                    if age_group_value is not None:
                        try:
                            age_group_str = str(age_group_value).strip()
                            if age_group_str:
                                try:
                                    case.age_group = AgeGroup(age_group_str)
                                except (ValueError, KeyError):
                                    try:
                                        case.age_group = AgeGroup[age_group_str]
                                    except (ValueError, KeyError) as e:
                                        print(f"[IMPORT] Warning: Could not set age_group to '{age_group_str}' (type: {type(age_group_value).__name__}): {e}")
                                except Exception as e:
                                    print(f"[IMPORT] Warning: Unexpected error setting age_group to '{age_group_str}': {e}")
                        except Exception as e:
                            print(f"[IMPORT] Warning: Could not process age_group value {age_group_value}: {e}")
                
                # Map created_by_user_id from backup using ID mapping
                # For FRCR Examiner: Always use current_user.id
                # For FRCR Revision: Use user_id_map to preserve original ownership
                if is_frcr_examiner:
                    case.created_by_user_id = current_user.id
                else:
                    if filtered_data.get('created_by_user_id'):
                        old_user_id = filtered_data.get('created_by_user_id')
                        case.created_by_user_id = user_id_map.get(old_user_id, current_user.id)
                if filtered_data.get('created_at'):
                    try:
                        if isinstance(filtered_data['created_at'], str):
                            case.created_at = datetime.fromisoformat(filtered_data['created_at'])
                        elif isinstance(filtered_data['created_at'], datetime):
                            case.created_at = filtered_data['created_at']
                    except (ValueError, TypeError) as e:
                        print(f"[IMPORT] Warning: Could not parse case created_at datetime: {filtered_data.get('created_at')}, error: {e}")
                
                db.session.add(case)
                try:
                    db.session.flush()
                except Exception as flush_error:
                    db.session.rollback()
                    print(f"[IMPORT] ERROR during case flush: {flush_error}")
                    print(f"[IMPORT] Case data that failed: case_number={filtered_data.get('case_number')}, module={filtered_data.get('module')}, body_part={filtered_data.get('body_part')}, age_group={filtered_data.get('age_group')}")
                    import traceback
                    traceback.print_exc()
                    raise
        
                # Add Q&A
                questions_list = case_data.get('questions', [])
                if isinstance(questions_list, list):
                    for q_data in questions_list:
                        if not isinstance(q_data, dict):
                            print(f"[IMPORT] Warning: Skipping invalid question data (not a dict)")
                            continue
                        question = Question(
                            case_id=case.id,
                            question_number=q_data.get('question_number', 0),
                            question_text=q_data.get('question_text', ''),
                        )
                        db.session.add(question)
                        stats['questions']['added'] += 1
                
                # Add answers
                answers_list = case_data.get('answers', [])
                if isinstance(answers_list, list):
                    for a_data in answers_list:
                        if not isinstance(a_data, dict):
                            print(f"[IMPORT] Warning: Skipping invalid answer data (not a dict)")
                            continue
                        answer = Answer(
                            case_id=case.id,
                            answer_number=a_data.get('answer_number', 0),
                            answer_text=a_data.get('answer_text', ''),
                        )
                        db.session.add(answer)
                        stats['answers']['added'] += 1
                
                # Add images
                import base64
                images_list = case_data.get('images', [])
                if isinstance(images_list, list):
                    for img_data in images_list:
                        if not isinstance(img_data, dict):
                            print(f"[IMPORT] Warning: Skipping invalid image data (not a dict)")
                            continue
                        image_data_binary = None
                        if img_data.get('image_data'):
                            try:
                                image_data_binary = base64.b64decode(img_data['image_data'])
                            except Exception as e:
                                print(f"[IMPORT] Warning: Failed to decode image data: {e}")
                                continue
                        
                        # Support both field name formats
                        image_filename = img_data.get('image_filename') or img_data.get('filename', '')
                        image_description = img_data.get('image_description') or img_data.get('description', '')
                        image_type = img_data.get('image_type', 'image/jpeg')
                        
                        # Check for Cloudinary URL (preferred) or binary data (legacy)
                        image_url = img_data.get('image_url')
                        image_public_id = img_data.get('image_public_id')
                        image_thumbnail_url = img_data.get('image_thumbnail_url')
                        
                        # Only create image if we have image data OR Cloudinary URL
                        if image_data_binary or image_url:
                            image = CaseImage(
                                case_id=case.id,
                                image_filename=image_filename,
                                image_type=image_type,
                                image_description=image_description,
                                image_data=image_data_binary,
                                image_url=image_url,
                                image_public_id=image_public_id,
                                image_thumbnail_url=image_thumbnail_url,
                            )
                            db.session.add(image)
                            stats['images']['added'] += 1
                
                stats['cases']['added'] += 1
                new_case_id = case.id
            
            # Store case ID mapping (for both new and existing cases)
            if old_case_id and new_case_id:
                case_id_map[old_case_id] = new_case_id
            
            # Commit in batches to avoid long transactions
            if (case_idx + 1) % CASE_BATCH_SIZE == 0:
                try:
                    db.session.commit()
                    print(f"[IMPORT] Committed batch of {CASE_BATCH_SIZE} cases ({case_idx + 1}/{len(cases_list)})")
                except Exception as batch_error:
                    db.session.rollback()
                    error_str = str(batch_error).lower()
                    print(f"[IMPORT] ERROR during case batch commit: {batch_error}")
                    print(f"[IMPORT] Case data that failed: case_number={filtered_data.get('case_number')}, module={filtered_data.get('module')}, body_part={filtered_data.get('body_part')}, age_group={filtered_data.get('age_group')}")
                    import traceback
                    traceback.print_exc()
                    if 'timeout' in error_str or 'connection' in error_str or 'disturbed' in error_str or 'locked' in error_str:
                        raise Exception('Database connection issue during case import. Please try again or split the import into smaller batches.')
                    raise
        
        # Final commit for any remaining cases
        try:
            db.session.commit()
            print(f"[IMPORT] Final commit completed for remaining cases")
        except Exception as commit_error:
            db.session.rollback()
            error_str = str(commit_error).lower()
            print(f"[IMPORT] ERROR during final case commit: {commit_error}")
            print(f"[IMPORT] Case data that failed: case_number={filtered_data.get('case_number')}, module={filtered_data.get('module')}, body_part={filtered_data.get('body_part')}, age_group={filtered_data.get('age_group')}")
            import traceback
            traceback.print_exc()
            if 'timeout' in error_str or 'connection' in error_str or 'disturbed' in error_str or 'locked' in error_str:
                raise Exception('Database connection issue during case import. Please try again or split the import into smaller batches.')
            raise
        
        # Import images from separate case_images array (FRCR Examiner format)
        # This handles backups where images are stored separately, not in case['images']
        # Note: Images for staging cases are already stored in enrichment_notes during case import
        # This section only processes images for cases that went directly to production
        case_images_list = backup_data.get('case_images', [])
        if isinstance(case_images_list, list) and len(case_images_list) > 0:
            import base64
            print(f"[IMPORT] Found {len(case_images_list)} images in separate case_images array")
            print(f"[IMPORT] Case ID map contains {len(case_id_map)} mappings: {case_id_map}")
            print(f"[IMPORT] Staging ID map contains {len(staging_id_map)} mappings: {staging_id_map}")
            for img_data in case_images_list:
                if not isinstance(img_data, dict):
                    print(f"[IMPORT] Warning: Skipping invalid image data (not a dict)")
                    continue
                
                # Map old case_id to new case_id
                old_case_id = img_data.get('case_id')
                if not old_case_id:
                    print(f"[IMPORT] Warning: Skipping image without case_id")
                    continue
                
                # Check if this is a staging case (images already stored in enrichment_notes)
                if old_case_id in staging_id_map:
                    print(f"[IMPORT] Skipping image for case_id {old_case_id} (already stored in staging case {staging_id_map[old_case_id]} enrichment_notes)")
                    continue
                
                new_case_id = case_id_map.get(old_case_id)
                if not new_case_id:
                    print(f"[IMPORT] Warning: Skipping image for case_id {old_case_id} (case not imported or not in case_id_map)")
                    print(f"[IMPORT] Available case IDs in map: {list(case_id_map.keys())}")
                    continue
                
                # Check if image already exists (if overwriting)
                if overwrite_existing:
                    CaseImage.query.filter_by(case_id=new_case_id, image_filename=img_data.get('image_filename') or img_data.get('filename', '')).delete()
                
                # Handle field name mapping: FRCR Examiner uses 'image_filename' and 'image_description'
                # Support both formats: 'image_filename'/'image_description' (FRCR Examiner) and 'filename'/'description' (FRCR Revision)
                image_filename = img_data.get('image_filename') or img_data.get('filename', '')
                image_description = img_data.get('image_description') or img_data.get('description', '')
                image_type = img_data.get('image_type', 'image/jpeg')
                
                # Decode image data (legacy binary)
                image_data_binary = None
                if img_data.get('image_data'):
                    try:
                        image_data_binary = base64.b64decode(img_data['image_data'])
                    except Exception as e:
                        print(f"[IMPORT] Warning: Failed to decode image data for {image_filename}: {e}")
                
                # Check for Cloudinary URL (preferred) or binary data (legacy)
                image_url = img_data.get('image_url')
                image_public_id = img_data.get('image_public_id')
                image_thumbnail_url = img_data.get('image_thumbnail_url')
                
                # Only create image if we have image data OR Cloudinary URL
                if image_data_binary or image_url:
                    image = CaseImage(
                        case_id=new_case_id,
                        image_filename=image_filename,
                        image_type=image_type,
                        image_description=image_description,
                        image_data=image_data_binary,
                        image_url=image_url,
                        image_public_id=image_public_id,
                        image_thumbnail_url=image_thumbnail_url,
                    )
                    db.session.add(image)
                    stats['images']['added'] += 1
                    print(f"[IMPORT] Added image {image_filename} to case {new_case_id}")
        
        try:
            db.session.commit()
        except Exception as commit_error:
            db.session.rollback()
            print(f"[IMPORT] ERROR during image commit: {commit_error}")
            import traceback
            traceback.print_exc()
            raise
        
        # Import revision sessions
        # For FRCR Examiner: Skip user-specific data (sessions, flags, highlights, notes)
        # For FRCR Revision: Import all user data
        if not is_frcr_examiner:
            for session_data in backup_data.get('revision_sessions', []):
                # Map user_id from backup using ID mapping
                old_user_id = session_data.get('user_id')
                user_id = user_id_map.get(old_user_id) if old_user_id else current_user.id
                
                if not user_id:
                    stats['revision_sessions']['skipped'] += 1
                    continue
                
                # Map case_ids from backup (old IDs -> new IDs)
                old_case_ids = session_data.get('case_ids', [])
                case_ids = [case_id_map.get(cid) for cid in old_case_ids if case_id_map.get(cid)]
                
                if not case_ids:
                    stats['revision_sessions']['skipped'] += 1
                    continue
                
                # Check if session already exists
                existing = RevisionSession.query.filter_by(user_id=user_id).first()
                if existing and not overwrite_existing:
                    stats['revision_sessions']['skipped'] += 1
                    continue
                
                if existing and overwrite_existing:
                    existing.set_case_ids_list(case_ids)
                    existing.current_case_index = session_data.get('current_case_index', 0)
                    # Update created_at if provided
                    if session_data.get('created_at'):
                        try:
                            if isinstance(session_data['created_at'], str):
                                existing.created_at = datetime.fromisoformat(session_data['created_at'])
                            elif isinstance(session_data['created_at'], datetime):
                                existing.created_at = session_data['created_at']
                        except (ValueError, TypeError) as e:
                            print(f"[IMPORT] Warning: Could not parse session created_at datetime: {session_data.get('created_at')}, error: {e}")
                    stats['revision_sessions']['added'] += 1
                else:
                    # Create new session - case_ids is required (nullable=False), so provide empty JSON array initially
                    rev_session = RevisionSession(
                        user_id=user_id,
                        case_ids='[]',  # Will be set by set_case_ids_list below
                        current_case_index=session_data.get('current_case_index', 0),
                    )
                    rev_session.set_case_ids_list(case_ids)
                    # Set created_at if provided in backup data
                    if session_data.get('created_at'):
                        try:
                            if isinstance(session_data['created_at'], str):
                                rev_session.created_at = datetime.fromisoformat(session_data['created_at'])
                            elif isinstance(session_data['created_at'], datetime):
                                rev_session.created_at = session_data['created_at']
                        except (ValueError, TypeError) as e:
                            print(f"[IMPORT] Warning: Could not parse session created_at datetime: {session_data.get('created_at')}, error: {e}")
                    db.session.add(rev_session)
                    stats['revision_sessions']['added'] += 1
        
        # Import case flags
        # For FRCR Examiner: Skip user-specific data
        if not is_frcr_examiner:
            for flag_data in backup_data.get('case_flags', []):
                # Map user_id and case_id from backup using ID mappings
                old_user_id = flag_data.get('user_id')
                old_case_id = flag_data.get('case_id')
                
                user_id = user_id_map.get(old_user_id) if old_user_id else None
                case_id = case_id_map.get(old_case_id) if old_case_id else None
                
                # Validate mapped IDs exist
                if not user_id or not User.query.get(user_id):
                    stats['case_flags']['skipped'] += 1
                    continue
                if not case_id or not Case.query.get(case_id):
                    stats['case_flags']['skipped'] += 1
                    continue
                
                # Check if flag already exists
                existing = CaseFlag.query.filter_by(user_id=user_id, case_id=case_id).first()
                if existing:
                    if overwrite_existing:
                        # Update timestamp if overwriting
                        if flag_data.get('created_at'):
                            try:
                                if isinstance(flag_data['created_at'], str):
                                    existing.created_at = datetime.fromisoformat(flag_data['created_at'])
                                elif isinstance(flag_data['created_at'], datetime):
                                    existing.created_at = flag_data['created_at']
                            except (ValueError, TypeError) as e:
                                print(f"[IMPORT] Warning: Could not parse flag created_at datetime: {flag_data.get('created_at')}, error: {e}")
                        stats['case_flags']['added'] += 1
                    else:
                        stats['case_flags']['skipped'] += 1
                    continue
                
                flag = CaseFlag(
                    user_id=user_id,
                    case_id=case_id,
                )
                if flag_data.get('created_at'):
                    try:
                        if isinstance(flag_data['created_at'], str):
                            flag.created_at = datetime.fromisoformat(flag_data['created_at'])
                        elif isinstance(flag_data['created_at'], datetime):
                            flag.created_at = flag_data['created_at']
                    except (ValueError, TypeError) as e:
                        print(f"[IMPORT] Warning: Could not parse flag created_at datetime: {flag_data.get('created_at')}, error: {e}")
                db.session.add(flag)
                stats['case_flags']['added'] += 1
        
        # Import highlights with batch commits (every 100 records)
        # For FRCR Examiner: Skip user-specific data
        BATCH_SIZE = 100  # Commit every 100 records to avoid long transactions
        if not is_frcr_examiner:
            highlights_list = backup_data.get('highlights', [])
            for idx, highlight_data in enumerate(highlights_list):
                # Map user_id and case_id from backup using ID mappings
                old_user_id = highlight_data.get('user_id')
                old_case_id = highlight_data.get('case_id')
                
                user_id = user_id_map.get(old_user_id) if old_user_id else None
                case_id = case_id_map.get(old_case_id) if old_case_id else None
                
                # Validate mapped IDs exist
                if not user_id or not User.query.get(user_id):
                    continue
                if not case_id or not Case.query.get(case_id):
                    continue
                
                highlight = TextHighlight(
                    user_id=user_id,
                    case_id=case_id,
                    text_content=highlight_data.get('text_content', ''),
                    highlight_color=highlight_data.get('highlight_color', 'yellow'),
                    field_name=highlight_data.get('field_name', 'discussion'),
                )
                if highlight_data.get('created_at'):
                    try:
                        if isinstance(highlight_data['created_at'], str):
                            highlight.created_at = datetime.fromisoformat(highlight_data['created_at'])
                        elif isinstance(highlight_data['created_at'], datetime):
                            highlight.created_at = highlight_data['created_at']
                    except (ValueError, TypeError) as e:
                        print(f"[IMPORT] Warning: Could not parse highlight created_at datetime: {highlight_data.get('created_at')}, error: {e}")
                db.session.add(highlight)
                stats['highlights']['added'] += 1
                
                # Commit in batches to avoid long transactions
                if (idx + 1) % BATCH_SIZE == 0:
                    try:
                        db.session.commit()
                        print(f"[IMPORT] Committed batch of {BATCH_SIZE} highlights ({idx + 1}/{len(highlights_list)})")
                    except Exception as batch_error:
                        db.session.rollback()
                        error_str = str(batch_error).lower()
                        print(f"[IMPORT] ERROR during highlights batch commit: {batch_error}")
                        if 'timeout' in error_str or 'connection' in error_str or 'disturbed' in error_str or 'locked' in error_str:
                            raise Exception('Database connection issue during import. Please try again or split the import into smaller batches.')
                        raise
        
        # Import notes with batch commits (every 100 records)
        # For FRCR Examiner: Skip user-specific data
        if not is_frcr_examiner:
            notes_list = backup_data.get('notes', [])
            for idx, note_data in enumerate(notes_list):
                # Map user_id and case_id from backup using ID mappings
                old_user_id = note_data.get('user_id')
                old_case_id = note_data.get('case_id')
                
                user_id = user_id_map.get(old_user_id) if old_user_id else None
                case_id = case_id_map.get(old_case_id) if old_case_id else None
                
                # Validate mapped IDs exist
                if not user_id or not User.query.get(user_id):
                    continue
                if not case_id or not Case.query.get(case_id):
                    continue
                
                note = CandidateNote(
                    user_id=user_id,
                    case_id=case_id,
                    note_text=note_data.get('note_text', ''),
                )
                if note_data.get('created_at'):
                    try:
                        if isinstance(note_data['created_at'], str):
                            note.created_at = datetime.fromisoformat(note_data['created_at'])
                        elif isinstance(note_data['created_at'], datetime):
                            note.created_at = note_data['created_at']
                    except (ValueError, TypeError) as e:
                        print(f"[IMPORT] Warning: Could not parse note created_at datetime: {note_data.get('created_at')}, error: {e}")
                db.session.add(note)
                stats['notes']['added'] += 1
                
                # Commit in batches to avoid long transactions
                if (idx + 1) % BATCH_SIZE == 0:
                    try:
                        db.session.commit()
                        print(f"[IMPORT] Committed batch of {BATCH_SIZE} notes ({idx + 1}/{len(notes_list)})")
                    except Exception as batch_error:
                        db.session.rollback()
                        error_str = str(batch_error).lower()
                        print(f"[IMPORT] ERROR during notes batch commit: {batch_error}")
                        if 'timeout' in error_str or 'connection' in error_str or 'disturbed' in error_str or 'locked' in error_str:
                            raise Exception('Database connection issue during import. Please try again or split the import into smaller batches.')
                        raise
        
        # Final commit for any remaining highlights/notes
        # For PostgreSQL: Handle connection timeouts and transaction issues
        try:
            db.session.commit()
            print(f"[IMPORT] Final commit completed for remaining highlights/notes")
        except Exception as commit_error:
            db.session.rollback()
            error_str = str(commit_error).lower()
            print(f"[IMPORT] ERROR during final commit: {commit_error}")
            import traceback
            traceback.print_exc()
            
            # Check for PostgreSQL-specific errors including "disturbed" or "locked"
            if 'timeout' in error_str or 'connection' in error_str or 'disturbed' in error_str or 'locked' in error_str:
                raise Exception('Database connection timeout or body error. The import may be too large or the connection was interrupted. Please try importing in smaller batches.')
            elif 'deadlock' in error_str or 'lock' in error_str:
                raise Exception('Database transaction conflict. Please try again in a few moments.')
            else:
                raise
        
        # Import revision history
        stats['revision_history'] = {'added': 0, 'skipped': 0}
        if not is_frcr_examiner:
            revision_history_list = backup_data.get('revision_history', [])
            for history_data in revision_history_list:
                old_user_id = history_data.get('user_id')
                old_case_id = history_data.get('case_id')
                
                user_id = user_id_map.get(old_user_id) if old_user_id else None
                case_id = case_id_map.get(old_case_id) if old_case_id else None
                
                if not user_id or not case_id:
                    stats['revision_history']['skipped'] += 1
                    continue
                
                # Check for existing history
                existing = RevisionHistory.query.filter_by(user_id=user_id, case_id=case_id).first()
                if existing:
                    stats['revision_history']['skipped'] += 1
                    continue
                
                history = RevisionHistory(
                    user_id=user_id,
                    case_id=case_id,
                    times_seen=history_data.get('times_seen', 0),
                )
                if history_data.get('module'):
                    try:
                        history.module = FRCRModule(history_data['module'])
                    except (ValueError, KeyError):
                        pass
                if history_data.get('first_seen_at'):
                    try:
                        history.first_seen_at = datetime.fromisoformat(history_data['first_seen_at']) if isinstance(history_data['first_seen_at'], str) else history_data['first_seen_at']
                    except (ValueError, TypeError):
                        pass
                if history_data.get('last_seen_at'):
                    try:
                        history.last_seen_at = datetime.fromisoformat(history_data['last_seen_at']) if isinstance(history_data['last_seen_at'], str) else history_data['last_seen_at']
                    except (ValueError, TypeError):
                        pass
                
                db.session.add(history)
                stats['revision_history']['added'] += 1
            
            try:
                db.session.commit()
                print(f"[IMPORT] Revision history imported: {stats['revision_history']['added']} records")
            except Exception as e:
                db.session.rollback()
                print(f"[IMPORT] ERROR during revision history commit: {e}")
        
        # Import forum messages
        forum_message_id_map = {}  # Map old message IDs to new message IDs
        stats['forum_messages'] = {'added': 0, 'skipped': 0}
        stats['forum_votes'] = {'added': 0, 'skipped': 0}
        stats['forum_flags'] = {'added': 0, 'skipped': 0}
        
        if not is_frcr_examiner:
            forum_messages_list = backup_data.get('forum_messages', [])
            for idx, msg_data in enumerate(forum_messages_list):
                old_msg_id = msg_data.get('id')
                old_user_id = msg_data.get('user_id')
                old_case_id = msg_data.get('case_id')
                
                user_id = user_id_map.get(old_user_id) if old_user_id else None
                case_id = case_id_map.get(old_case_id) if old_case_id else None
                
                # Validate mapped IDs exist
                if not user_id or not User.query.get(user_id):
                    stats['forum_messages']['skipped'] += 1
                    continue
                if not case_id or not Case.query.get(case_id):
                    stats['forum_messages']['skipped'] += 1
                    continue
                
                forum_msg = ForumMessage(
                    case_id=case_id,
                    user_id=user_id,
                    content=msg_data.get('content', ''),
                    vote_score=msg_data.get('vote_score', 0),
                    is_pinned=msg_data.get('is_pinned', False),
                    flag_count=msg_data.get('flag_count', 0),
                    image_url=msg_data.get('image_url'),
                    image_public_id=msg_data.get('image_public_id'),
                    image_thumbnail_url=msg_data.get('image_thumbnail_url'),
                )
                if msg_data.get('created_at'):
                    try:
                        forum_msg.created_at = datetime.fromisoformat(msg_data['created_at']) if isinstance(msg_data['created_at'], str) else msg_data['created_at']
                    except (ValueError, TypeError):
                        pass
                if msg_data.get('updated_at'):
                    try:
                        forum_msg.updated_at = datetime.fromisoformat(msg_data['updated_at']) if isinstance(msg_data['updated_at'], str) else msg_data['updated_at']
                    except (ValueError, TypeError):
                        pass
                
                db.session.add(forum_msg)
                db.session.flush()  # Get the new ID
                
                if old_msg_id:
                    forum_message_id_map[old_msg_id] = forum_msg.id
                
                stats['forum_messages']['added'] += 1
                
                # Commit in batches
                if (idx + 1) % BATCH_SIZE == 0:
                    try:
                        db.session.commit()
                        print(f"[IMPORT] Committed batch of forum messages ({idx + 1}/{len(forum_messages_list)})")
                    except Exception as batch_error:
                        db.session.rollback()
                        print(f"[IMPORT] ERROR during forum messages batch commit: {batch_error}")
            
            # Import forum votes
            forum_votes_list = backup_data.get('forum_votes', [])
            for vote_data in forum_votes_list:
                old_msg_id = vote_data.get('message_id')
                old_user_id = vote_data.get('user_id')
                
                message_id = forum_message_id_map.get(old_msg_id)
                user_id = user_id_map.get(old_user_id) if old_user_id else None
                
                if not message_id or not user_id:
                    stats['forum_votes']['skipped'] += 1
                    continue
                
                # Check for existing vote
                existing_vote = ForumMessageVote.query.filter_by(message_id=message_id, user_id=user_id).first()
                if existing_vote:
                    stats['forum_votes']['skipped'] += 1
                    continue
                
                vote = ForumMessageVote(
                    message_id=message_id,
                    user_id=user_id,
                    vote_value=vote_data.get('vote_value', 0),
                )
                if vote_data.get('created_at'):
                    try:
                        vote.created_at = datetime.fromisoformat(vote_data['created_at']) if isinstance(vote_data['created_at'], str) else vote_data['created_at']
                    except (ValueError, TypeError):
                        pass
                
                db.session.add(vote)
                stats['forum_votes']['added'] += 1
            
            # Import forum flags
            forum_flags_list = backup_data.get('forum_flags', [])
            for flag_data in forum_flags_list:
                old_msg_id = flag_data.get('message_id')
                old_user_id = flag_data.get('user_id')
                
                message_id = forum_message_id_map.get(old_msg_id)
                user_id = user_id_map.get(old_user_id) if old_user_id else None
                
                if not message_id or not user_id:
                    stats['forum_flags']['skipped'] += 1
                    continue
                
                # Check for existing flag
                existing_flag = ForumMessageFlag.query.filter_by(message_id=message_id, user_id=user_id).first()
                if existing_flag:
                    stats['forum_flags']['skipped'] += 1
                    continue
                
                flag = ForumMessageFlag(
                    message_id=message_id,
                    user_id=user_id,
                    reason=flag_data.get('reason', 'other'),
                    details=flag_data.get('details'),
                )
                if flag_data.get('created_at'):
                    try:
                        flag.created_at = datetime.fromisoformat(flag_data['created_at']) if isinstance(flag_data['created_at'], str) else flag_data['created_at']
                    except (ValueError, TypeError):
                        pass
                
                db.session.add(flag)
                stats['forum_flags']['added'] += 1
            
            # Final commit for forum data
            try:
                db.session.commit()
                print(f"[IMPORT] Forum data imported: {stats['forum_messages']['added']} messages, {stats['forum_votes']['added']} votes, {stats['forum_flags']['added']} flags")
            except Exception as forum_error:
                db.session.rollback()
                print(f"[IMPORT] ERROR during forum commit: {forum_error}")
        
        # ==================== IMPORT AJCC TNM DATA ====================
        stats['ajcc_body_sections'] = {'added': 0, 'updated': 0, 'skipped': 0}
        stats['ajcc_disease_sites'] = {'added': 0, 'updated': 0, 'skipped': 0}
        stats['ajcc_diagnosis_years'] = {'added': 0, 'skipped': 0}
        stats['ajcc_staging_data'] = {'added': 0, 'updated': 0, 'skipped': 0}
        stats['ajcc_disease_mappings'] = {'added': 0, 'skipped': 0}
        stats['ajcc_staging_time_prefixes'] = {'added': 0, 'skipped': 0}
        
        # Maps for ID translation during import
        ajcc_section_id_map = {}  # old section_id -> new section_id
        ajcc_disease_id_map = {}  # old disease_id -> new disease_id
        ajcc_year_id_map = {}  # old year_id -> new year_id
        
        # Import AJCC Body Sections
        for section_data in backup_data.get('ajcc_body_sections', []):
            if not isinstance(section_data, dict):
                continue
            
            old_id = section_data.get('id')
            slug = section_data.get('slug')
            
            if not slug:
                continue
            
            existing = AJCCBodySection.query.filter_by(slug=slug).first()
            if existing:
                if overwrite_existing:
                    existing.section_name = section_data.get('section_name', existing.section_name)
                    existing.display_order = section_data.get('display_order', existing.display_order)
                    stats['ajcc_body_sections']['updated'] += 1
                else:
                    stats['ajcc_body_sections']['skipped'] += 1
                if old_id:
                    ajcc_section_id_map[old_id] = existing.id
            else:
                section = AJCCBodySection(
                    section_name=section_data.get('section_name', ''),
                    slug=slug,
                    display_order=section_data.get('display_order', 0),
                )
                db.session.add(section)
                db.session.flush()
                if old_id:
                    ajcc_section_id_map[old_id] = section.id
                stats['ajcc_body_sections']['added'] += 1
        
        # Import AJCC Disease Sites
        for disease_data in backup_data.get('ajcc_disease_sites', []):
            if not isinstance(disease_data, dict):
                continue
            
            old_id = disease_data.get('id')
            slug = disease_data.get('slug')
            old_section_id = disease_data.get('body_section_id')
            
            if not slug:
                continue
            
            # Map section_id from backup to new ID
            new_section_id = ajcc_section_id_map.get(old_section_id)
            if not new_section_id:
                # Try to find section by looking up existing sections
                print(f"[IMPORT] Warning: Could not map body_section_id {old_section_id} for disease {slug}")
                continue
            
            existing = AJCCDiseaseSite.query.filter_by(slug=slug, body_section_id=new_section_id).first()
            if existing:
                if overwrite_existing:
                    existing.disease_name = disease_data.get('disease_name', existing.disease_name)
                    existing.ajcc_url_path = disease_data.get('ajcc_url_path', existing.ajcc_url_path)
                    if 'display_order' in disease_data:
                        existing.display_order = disease_data.get('display_order', 0)
                    if disease_data.get('frcr_module') is not None:
                        existing.frcr_module = disease_data.get('frcr_module')
                    if disease_data.get('frcr_body_part') is not None:
                        existing.frcr_body_part = disease_data.get('frcr_body_part')
                    if disease_data.get('frcr_age_group') is not None:
                        existing.frcr_age_group = disease_data.get('frcr_age_group')
                    stats['ajcc_disease_sites']['updated'] += 1
                else:
                    stats['ajcc_disease_sites']['skipped'] += 1
                if old_id:
                    ajcc_disease_id_map[old_id] = existing.id
            else:
                disease = AJCCDiseaseSite(
                    body_section_id=new_section_id,
                    disease_name=disease_data.get('disease_name', ''),
                    slug=slug,
                    ajcc_url_path=disease_data.get('ajcc_url_path'),
                    display_order=disease_data.get('display_order', 0),
                    frcr_module=disease_data.get('frcr_module'),
                    frcr_body_part=disease_data.get('frcr_body_part'),
                    frcr_age_group=disease_data.get('frcr_age_group'),
                )
                db.session.add(disease)
                db.session.flush()
                if old_id:
                    ajcc_disease_id_map[old_id] = disease.id
                stats['ajcc_disease_sites']['added'] += 1
        
        # Import AJCC Diagnosis Years
        for year_data in backup_data.get('ajcc_diagnosis_years', []):
            if not isinstance(year_data, dict):
                continue
            
            old_id = year_data.get('id')
            year_value = year_data.get('year')
            
            if not year_value:
                continue
            
            existing = AJCCDiagnosisYear.query.filter_by(year=year_value).first()
            if existing:
                stats['ajcc_diagnosis_years']['skipped'] += 1
                if old_id:
                    ajcc_year_id_map[old_id] = existing.id
            else:
                year = AJCCDiagnosisYear(
                    year=year_value,
                    is_default=year_data.get('is_default', False),
                )
                db.session.add(year)
                db.session.flush()
                if old_id:
                    ajcc_year_id_map[old_id] = year.id
                stats['ajcc_diagnosis_years']['added'] += 1
        
        # Import AJCC Staging Data
        for staging_data in backup_data.get('ajcc_staging_data', []):
            if not isinstance(staging_data, dict):
                continue
            
            old_disease_id = staging_data.get('disease_site_id')
            old_year_id = staging_data.get('diagnosis_year_id')
            
            new_disease_id = ajcc_disease_id_map.get(old_disease_id)
            new_year_id = ajcc_year_id_map.get(old_year_id)
            
            if not new_disease_id or not new_year_id:
                print(f"[IMPORT] Warning: Could not map staging data - disease_id: {old_disease_id}->{new_disease_id}, year_id: {old_year_id}->{new_year_id}")
                stats['ajcc_staging_data']['skipped'] += 1
                continue
            
            existing = AJCCStagingData.query.filter_by(
                disease_site_id=new_disease_id,
                diagnosis_year_id=new_year_id
            ).first()
            
            # Column names to update
            json_columns = [
                'tnm_data_json', 'cancers_staged_json', 'cancers_not_staged_json',
                'summary_changes_json', 'primary_sites_json', 'histopathologic_types_json',
                'imaging_workup_json', 'staging_rules_json', 'common_scenarios_json', 'notes_json'
            ]
            html_columns = [
                'section_1_quick_reference_html', 'section_2_cancers_staged_html',
                'section_3_cancers_not_staged_html', 'section_4_summary_changes_html',
                'section_5_primary_site_html', 'section_6_histopathologic_type_html',
                'section_7_clinical_staging_workup_html', 'section_8_staging_rules_html',
                'section_9_common_scenarios_html', 'section_10_explanatory_notes_html'
            ]
            curated_columns = [
                'curated_quick_reference_html', 'curated_explanatory_notes_html'
            ]
            
            if existing:
                if overwrite_existing:
                    # Update all JSON, HTML, and curated columns
                    for col in json_columns + html_columns + curated_columns:
                        if staging_data.get(col) is not None:
                            setattr(existing, col, staging_data[col])
                    if staging_data.get('raw_html_content') is not None:
                        existing.raw_html_content = staging_data['raw_html_content']
                    if staging_data.get('data_version') is not None:
                        existing.data_version = staging_data['data_version']
                    if staging_data.get('curated_by_user_id') is not None:
                        old_uid = staging_data['curated_by_user_id']
                        existing.curated_by_user_id = user_id_map.get(old_uid) if old_uid else None
                    if staging_data.get('curated_at'):
                        try:
                            val = staging_data['curated_at']
                            existing.curated_at = datetime.fromisoformat(val.replace('Z', '+00:00')) if isinstance(val, str) else val
                        except (ValueError, TypeError):
                            pass
                    existing.last_updated_at = datetime.utcnow()
                    stats['ajcc_staging_data']['updated'] += 1
                else:
                    stats['ajcc_staging_data']['skipped'] += 1
            else:
                staging = AJCCStagingData(
                    disease_site_id=new_disease_id,
                    diagnosis_year_id=new_year_id,
                )
                # Set all JSON, HTML, and curated columns
                for col in json_columns + html_columns + curated_columns:
                    if staging_data.get(col) is not None:
                        setattr(staging, col, staging_data[col])
                if staging_data.get('raw_html_content') is not None:
                    staging.raw_html_content = staging_data['raw_html_content']
                if staging_data.get('data_version') is not None:
                    staging.data_version = staging_data['data_version']
                # Set extracted_at from backup
                if staging_data.get('extracted_at'):
                    try:
                        val = staging_data['extracted_at']
                        staging.extracted_at = datetime.fromisoformat(val.replace('Z', '+00:00')) if isinstance(val, str) else val
                    except (ValueError, TypeError):
                        pass
                # Set extracted_by_user_id and curated_by_user_id using user_id_map
                if staging_data.get('extracted_by_user_id'):
                    old_user_id = staging_data['extracted_by_user_id']
                    staging.extracted_by_user_id = user_id_map.get(old_user_id) if old_user_id else None
                if staging_data.get('curated_by_user_id'):
                    old_uid = staging_data['curated_by_user_id']
                    staging.curated_by_user_id = user_id_map.get(old_uid) if old_uid else None
                if staging_data.get('curated_at'):
                    try:
                        val = staging_data['curated_at']
                        staging.curated_at = datetime.fromisoformat(val.replace('Z', '+00:00')) if isinstance(val, str) else val
                    except (ValueError, TypeError):
                        pass
                db.session.add(staging)
                stats['ajcc_staging_data']['added'] += 1
        
        # Import AJCC Disease Mappings
        for mapping_data in backup_data.get('ajcc_disease_mappings', []):
            if not isinstance(mapping_data, dict):
                continue
            
            old_disease_id = mapping_data.get('disease_site_id')
            new_disease_id = ajcc_disease_id_map.get(old_disease_id)
            
            if not new_disease_id:
                stats['ajcc_disease_mappings']['skipped'] += 1
                continue
            
            # Check for existing mapping
            frcr_module_value = mapping_data.get('frcr_module')
            body_part_value = mapping_data.get('body_part')
            
            existing = AJCCDiseaseMapping.query.filter_by(disease_site_id=new_disease_id).first()
            if existing:
                stats['ajcc_disease_mappings']['skipped'] += 1
                continue
            
            mapping = AJCCDiseaseMapping(disease_site_id=new_disease_id)
            
            if frcr_module_value:
                try:
                    mapping.frcr_module = FRCRModule(frcr_module_value)
                except (ValueError, KeyError):
                    pass
            
            if body_part_value:
                try:
                    mapping.body_part = BodyPart(body_part_value)
                except (ValueError, KeyError):
                    pass
            
            # Add notes if present
            if mapping_data.get('notes'):
                mapping.notes = mapping_data['notes']
            
            db.session.add(mapping)
            stats['ajcc_disease_mappings']['added'] += 1
        
        # Import AJCC Staging Time Prefixes
        for prefix_data in backup_data.get('ajcc_staging_time_prefixes', []):
            if not isinstance(prefix_data, dict):
                continue
            
            prefix_value = prefix_data.get('prefix')
            if not prefix_value:
                continue
            
            existing = AJCCStagingTimePrefix.query.filter_by(prefix=prefix_value).first()
            if existing:
                stats['ajcc_staging_time_prefixes']['skipped'] += 1
                continue
            
            prefix = AJCCStagingTimePrefix(
                prefix=prefix_value,
                name=prefix_data.get('name', ''),
                description=prefix_data.get('description', ''),
                display_order=prefix_data.get('display_order', 0),
            )
            db.session.add(prefix)
            stats['ajcc_staging_time_prefixes']['added'] += 1
        
        # Import Intelligent TNM Data (AI-generated, human-verified)
        stats['intelligent_tnm_data'] = {'added': 0, 'updated': 0, 'skipped': 0}
        for intel_data in backup_data.get('intelligent_tnm_data', []):
            if not isinstance(intel_data, dict):
                continue
            
            old_disease_id = intel_data.get('disease_site_id')
            old_year_id = intel_data.get('diagnosis_year_id')
            
            new_disease_id = ajcc_disease_id_map.get(old_disease_id)
            new_year_id = ajcc_year_id_map.get(old_year_id) if old_year_id else None
            
            if not new_disease_id:
                stats['intelligent_tnm_data']['skipped'] += 1
                continue
            
            # Query by disease_site_id only - one record per disease site
            # (unique constraint is on disease_site_id, not disease_site_id + diagnosis_year_id)
            existing = IntelligentTNMData.query.filter_by(
                disease_site_id=new_disease_id
            ).first()
            
            if existing:
                if overwrite_existing:
                    existing.tnm_memory_aid_t = intel_data.get('tnm_memory_aid_t')
                    existing.tnm_memory_aid_n = intel_data.get('tnm_memory_aid_n')
                    existing.tnm_memory_aid_m = intel_data.get('tnm_memory_aid_m')
                    existing.radiologist_key_points_json = intel_data.get('radiologist_key_points_json')
                    existing.upstaging_triggers_json = intel_data.get('upstaging_triggers_json')
                    existing.mdt_critical_findings_json = intel_data.get('mdt_critical_findings_json')
                    existing.copy_blocks_json = intel_data.get('copy_blocks_json')
                    existing.imaging_checklist_json = intel_data.get('imaging_checklist_json')
                    existing.reference_images_json = intel_data.get('reference_images_json')
                    existing.warnings_json = intel_data.get('warnings_json')
                    existing.version = intel_data.get('version', 1)
                    # Update diagnosis_year_id if provided
                    if new_year_id:
                        existing.diagnosis_year_id = new_year_id
                    stats['intelligent_tnm_data']['updated'] += 1
                else:
                    stats['intelligent_tnm_data']['skipped'] += 1
            else:
                intel = IntelligentTNMData(
                    disease_site_id=new_disease_id,
                    diagnosis_year_id=new_year_id,
                    tnm_memory_aid_t=intel_data.get('tnm_memory_aid_t'),
                    tnm_memory_aid_n=intel_data.get('tnm_memory_aid_n'),
                    tnm_memory_aid_m=intel_data.get('tnm_memory_aid_m'),
                    radiologist_key_points_json=intel_data.get('radiologist_key_points_json'),
                    upstaging_triggers_json=intel_data.get('upstaging_triggers_json'),
                    mdt_critical_findings_json=intel_data.get('mdt_critical_findings_json'),
                    copy_blocks_json=intel_data.get('copy_blocks_json'),
                    imaging_checklist_json=intel_data.get('imaging_checklist_json'),
                    reference_images_json=intel_data.get('reference_images_json'),
                    warnings_json=intel_data.get('warnings_json'),
                    version=intel_data.get('version', 1),
                )
                # Map user IDs
                if intel_data.get('verified_by_user_id'):
                    intel.verified_by_user_id = user_id_map.get(intel_data['verified_by_user_id'])
                if intel_data.get('source_case_id'):
                    intel.source_case_id = case_id_map.get(intel_data['source_case_id'])
                db.session.add(intel)
                stats['intelligent_tnm_data']['added'] += 1
        
        # Import Case References (map case_id via case_id_map)
        stats['case_references'] = {'added': 0, 'updated': 0, 'skipped': 0}
        for ref_data in backup_data.get('case_references', []):
            if not isinstance(ref_data, dict):
                continue
            old_case_id = ref_data.get('case_id')
            new_case_id = case_id_map.get(old_case_id)
            if not new_case_id:
                stats['case_references']['skipped'] += 1
                continue
            existing = CaseReference.query.filter_by(case_id=new_case_id, ref_number=ref_data.get('ref_number')).first()
            if existing and not overwrite_existing:
                stats['case_references']['skipped'] += 1
                continue
            if existing and overwrite_existing:
                existing.title = ref_data.get('title', '')
                existing.url = ref_data.get('url', '')
                existing.journal = ref_data.get('journal')
                existing.year = ref_data.get('year')
                existing.is_inline = ref_data.get('is_inline', False)
                stats['case_references']['updated'] += 1
            else:
                ref = CaseReference(
                    case_id=new_case_id,
                    ref_number=ref_data.get('ref_number', 1),
                    title=ref_data.get('title', ''),
                    url=ref_data.get('url', ''),
                    journal=ref_data.get('journal'),
                    year=ref_data.get('year'),
                    is_inline=ref_data.get('is_inline', False),
                )
                db.session.add(ref)
                stats['case_references']['added'] += 1
        
        # Import Case Reference Images (map case_id via case_id_map, added_by_user_id via user_id_map)
        stats['case_reference_images'] = {'added': 0, 'updated': 0, 'skipped': 0}
        for img_data in backup_data.get('case_reference_images', []):
            if not isinstance(img_data, dict):
                continue
            old_case_id = img_data.get('case_id')
            new_case_id = case_id_map.get(old_case_id)
            if not new_case_id:
                stats['case_reference_images']['skipped'] += 1
                continue
            new_user_id = user_id_map.get(img_data.get('added_by_user_id')) if img_data.get('added_by_user_id') else None
            source_url = img_data.get('source_url', '')
            existing = CaseReferenceImage.query.filter_by(
                case_id=new_case_id,
                source_url=source_url,
            ).first() if source_url else None
            if existing and not overwrite_existing:
                stats['case_reference_images']['skipped'] += 1
                continue
            if existing and overwrite_existing:
                existing.source_domain = img_data.get('source_domain', '')
                existing.thumbnail_url = img_data.get('thumbnail_url')
                existing.image_type = img_data.get('image_type', 'ct_mri')
                existing.modality = img_data.get('modality')
                existing.ai_description = img_data.get('ai_description')
                existing.ai_relevance_score = img_data.get('ai_relevance_score')
                existing.admin_note = img_data.get('admin_note')
                existing.display_order = img_data.get('display_order', 0)
                existing.added_by_user_id = new_user_id
                existing.license = img_data.get('license', 'CC BY 4.0')
                existing.attribution = img_data.get('attribution', '')
                stats['case_reference_images']['updated'] += 1
            else:
                ref_img = CaseReferenceImage(
                    case_id=new_case_id,
                    source_url=source_url,
                    source_domain=img_data.get('source_domain', ''),
                    thumbnail_url=img_data.get('thumbnail_url'),
                    image_type=img_data.get('image_type', 'ct_mri'),
                    modality=img_data.get('modality'),
                    ai_description=img_data.get('ai_description'),
                    ai_relevance_score=img_data.get('ai_relevance_score'),
                    admin_note=img_data.get('admin_note'),
                    display_order=img_data.get('display_order', 0),
                    added_by_user_id=new_user_id,
                    license=img_data.get('license', 'CC BY 4.0'),
                    attribution=img_data.get('attribution', ''),
                )
                db.session.add(ref_img)
                stats['case_reference_images']['added'] += 1
        
        # Import TNM References (map disease_site_id via ajcc_disease_id_map)
        stats['tnm_references'] = {'added': 0, 'updated': 0, 'skipped': 0}
        for ref_data in backup_data.get('tnm_references', []):
            if not isinstance(ref_data, dict):
                continue
            old_disease_id = ref_data.get('disease_site_id')
            new_disease_id = ajcc_disease_id_map.get(old_disease_id)
            if not new_disease_id:
                stats['tnm_references']['skipped'] += 1
                continue
            existing = TnmReference.query.filter_by(disease_site_id=new_disease_id, ref_number=ref_data.get('ref_number')).first()
            if existing and not overwrite_existing:
                stats['tnm_references']['skipped'] += 1
                continue
            if existing and overwrite_existing:
                existing.title = ref_data.get('title', '')
                existing.url = ref_data.get('url', '')
                existing.journal = ref_data.get('journal')
                existing.year = ref_data.get('year')
                existing.is_inline = ref_data.get('is_inline', False)
                stats['tnm_references']['updated'] += 1
            else:
                ref = TnmReference(
                    disease_site_id=new_disease_id,
                    ref_number=ref_data.get('ref_number', 1),
                    title=ref_data.get('title', ''),
                    url=ref_data.get('url', ''),
                    journal=ref_data.get('journal'),
                    year=ref_data.get('year'),
                    is_inline=ref_data.get('is_inline', False),
                )
                db.session.add(ref)
                stats['tnm_references']['added'] += 1
        
        # Import Anatomy Figures (standalone - match by figure_id)
        stats['anatomy_figures'] = {'added': 0, 'updated': 0, 'skipped': 0}
        for fig_data in backup_data.get('anatomy_figures', []):
            if not isinstance(fig_data, dict):
                continue
            figure_id = fig_data.get('figure_id')
            if not figure_id:
                stats['anatomy_figures']['skipped'] += 1
                continue
            existing = AnatomyFigure.query.filter_by(figure_id=figure_id).first()
            if existing:
                if overwrite_existing:
                    for attr in ('title', 'description', 'source', 'body_region', 'figure_type', 'keywords', 'modality',
                                'cancer_type', 'staging_category', 'original_url', 'cloudinary_url', 'cloudinary_public_id',
                                'thumbnail_url', 'license', 'attribution', 'chapter', 'page_number', 'is_active'):
                        if fig_data.get(attr) is not None:
                            setattr(existing, attr, fig_data[attr])
                    stats['anatomy_figures']['updated'] += 1
                else:
                    stats['anatomy_figures']['skipped'] += 1
            else:
                fig = AnatomyFigure(
                    figure_id=figure_id,
                    title=fig_data.get('title', ''),
                    description=fig_data.get('description'),
                    source=fig_data.get('source', ''),
                    body_region=fig_data.get('body_region'),
                    figure_type=fig_data.get('figure_type'),
                    keywords=fig_data.get('keywords'),
                    modality=fig_data.get('modality'),
                    cancer_type=fig_data.get('cancer_type'),
                    staging_category=fig_data.get('staging_category'),
                    original_url=fig_data.get('original_url'),
                    cloudinary_url=fig_data.get('cloudinary_url'),
                    cloudinary_public_id=fig_data.get('cloudinary_public_id'),
                    thumbnail_url=fig_data.get('thumbnail_url'),
                    license=fig_data.get('license', 'CC BY 4.0'),
                    attribution=fig_data.get('attribution', ''),
                    chapter=fig_data.get('chapter'),
                    page_number=fig_data.get('page_number'),
                    is_active=fig_data.get('is_active', True),
                )
                db.session.add(fig)
                stats['anatomy_figures']['added'] += 1
        
        # Import TNM Images (map disease_site_id, diagnosis_year_id, uploaded_by_user_id)
        stats['tnm_images'] = {'added': 0, 'updated': 0, 'skipped': 0}
        for img_data in backup_data.get('tnm_images', []):
            if not isinstance(img_data, dict):
                continue
            old_disease_id = img_data.get('disease_site_id')
            new_disease_id = ajcc_disease_id_map.get(old_disease_id)
            if not new_disease_id:
                stats['tnm_images']['skipped'] += 1
                continue
            new_year_id = ajcc_year_id_map.get(img_data.get('diagnosis_year_id')) if img_data.get('diagnosis_year_id') else None
            new_user_id = user_id_map.get(img_data.get('uploaded_by_user_id')) if img_data.get('uploaded_by_user_id') else None
            cloudinary_public_id = img_data.get('cloudinary_public_id') or ''
            existing = TNMImage.query.filter_by(
                disease_site_id=new_disease_id,
                cloudinary_public_id=cloudinary_public_id,
            ).first() if cloudinary_public_id else None
            if existing and not overwrite_existing:
                stats['tnm_images']['skipped'] += 1
                continue
            if existing and overwrite_existing:
                existing.title = img_data.get('title')
                existing.description = img_data.get('description')
                existing.alt_text = img_data.get('alt_text')
                existing.diagnosis_year_id = new_year_id
                existing.width = img_data.get('width')
                existing.height = img_data.get('height')
                existing.image_type = img_data.get('image_type', 'reference')
                existing.uploaded_by_user_id = new_user_id
                existing.is_active = img_data.get('is_active', True)
                stats['tnm_images']['updated'] += 1
            else:
                img = TNMImage(
                    disease_site_id=new_disease_id,
                    diagnosis_year_id=new_year_id,
                    title=img_data.get('title'),
                    description=img_data.get('description'),
                    alt_text=img_data.get('alt_text'),
                    cloudinary_url=img_data.get('cloudinary_url', ''),
                    cloudinary_public_id=cloudinary_public_id,
                    width=img_data.get('width'),
                    height=img_data.get('height'),
                    image_type=img_data.get('image_type', 'reference'),
                    uploaded_by_user_id=new_user_id,
                    is_active=img_data.get('is_active', True),
                )
                db.session.add(img)
                stats['tnm_images']['added'] += 1
        
        # Import Case Image Stacks (OneDrive linked image folders + R2)
        stats['case_image_stacks'] = {'added': 0, 'updated': 0, 'skipped': 0}
        stack_id_map = {}  # old_stack_id -> new_stack_id
        for stack_data in backup_data.get('case_image_stacks', []):
            if not isinstance(stack_data, dict):
                continue
            old_case_id = stack_data.get('case_id')
            new_case_id = case_id_map.get(old_case_id)
            if not new_case_id:
                stats['case_image_stacks']['skipped'] += 1
                continue
            new_user_id = user_id_map.get(stack_data.get('created_by_user_id')) if stack_data.get('created_by_user_id') else None
            old_stack_id = stack_data.get('id')
            stack = CaseImageStack(
                case_id=new_case_id,
                study_label=stack_data.get('study_label'),
                onedrive_share_id=stack_data.get('onedrive_share_id') or None,
                onedrive_folder_path=stack_data.get('onedrive_folder_path'),
                config_json=stack_data.get('config_json', '{}'),
                storage_backend=stack_data.get('storage_backend') or 'onedrive',
                r2_config_json=stack_data.get('r2_config_json'),
                display_order=stack_data.get('display_order', 0),
                onedrive_refresh_token_encrypted=stack_data.get('onedrive_refresh_token_encrypted'),
                description_html=stack_data.get('description_html'),
                created_by_user_id=new_user_id,
            )
            db.session.add(stack)
            db.session.flush()
            if old_stack_id is not None:
                stack_id_map[old_stack_id] = stack.id
            stats['case_image_stacks']['added'] += 1
        
        # Import Case Image Annotations (Cornerstone.js annotations; per-study via stack_id)
        stats['case_image_annotations'] = {'added': 0, 'updated': 0, 'skipped': 0}
        for ann_data in backup_data.get('case_image_annotations', []):
            if not isinstance(ann_data, dict):
                continue
            old_case_id = ann_data.get('case_id')
            new_case_id = case_id_map.get(old_case_id)
            if not new_case_id:
                stats['case_image_annotations']['skipped'] += 1
                continue
            old_stack_id = ann_data.get('stack_id')
            new_stack_id = stack_id_map.get(old_stack_id) if old_stack_id is not None else None
            new_user_id = user_id_map.get(ann_data.get('created_by_user_id')) if ann_data.get('created_by_user_id') else None
            if new_stack_id:
                existing = CaseImageAnnotation.query.filter_by(stack_id=new_stack_id).first()
            else:
                existing = CaseImageAnnotation.query.filter_by(case_id=new_case_id).first()
            if existing and not overwrite_existing:
                stats['case_image_annotations']['skipped'] += 1
                continue
            if existing and overwrite_existing:
                existing.annotations_json = ann_data.get('annotations_json', '{}')
                existing.created_by_user_id = new_user_id
                stats['case_image_annotations']['updated'] += 1
            else:
                ann = CaseImageAnnotation(
                    case_id=new_case_id,
                    stack_id=new_stack_id,
                    annotations_json=ann_data.get('annotations_json', '{}'),
                    created_by_user_id=new_user_id,
                )
                db.session.add(ann)
                stats['case_image_annotations']['added'] += 1

        # Import TNM Calculator Content
        stats['tnm_calculator_content'] = {'added': 0, 'updated': 0, 'skipped': 0}
        for content_data in backup_data.get('tnm_calculator_content', []):
            slug = content_data.get('slug')
            if not slug:
                stats['tnm_calculator_content']['skipped'] += 1
                continue

            # Check if already exists by slug
            existing = TNMCalculatorContent.query.filter_by(slug=slug).first()

            # Map algorithm_case_id to new case ID if exists
            old_case_id = content_data.get('algorithm_case_id')
            new_case_id = case_id_map.get(old_case_id) if old_case_id else None

            # Map created_by_user_id
            old_user_id = content_data.get('created_by_user_id')
            new_user_id = user_id_map.get(old_user_id) if old_user_id else None

            if existing:
                # Update existing content
                existing.cancer_name = content_data.get('cancer_name', existing.cancer_name)
                existing.body_section = content_data.get('body_section', existing.body_section)
                existing.calculator_html = content_data.get('calculator_html', existing.calculator_html)
                existing.algorithm_discussion_html = content_data.get('algorithm_discussion_html', existing.algorithm_discussion_html)
                existing.staging_system = content_data.get('staging_system', existing.staging_system)
                existing.special_features = content_data.get('special_features', existing.special_features)
                existing.description = content_data.get('description', existing.description)
                existing.is_available = content_data.get('is_available', existing.is_available)
                existing.generation_model = content_data.get('generation_model', existing.generation_model)
                existing.algorithm_case_id = new_case_id
                existing.updated_at = _parse_datetime_for_sqlite(content_data.get('updated_at')) or datetime.utcnow()
                stats['tnm_calculator_content']['updated'] += 1
            else:
                # Create new content
                content = TNMCalculatorContent(
                    slug=slug,
                    cancer_name=content_data.get('cancer_name', ''),
                    body_section=content_data.get('body_section', ''),
                    calculator_html=content_data.get('calculator_html'),
                    algorithm_discussion_html=content_data.get('algorithm_discussion_html'),
                    staging_system=content_data.get('staging_system', 'AJCC 9th Edition'),
                    special_features=content_data.get('special_features'),
                    description=content_data.get('description'),
                    is_available=content_data.get('is_available', False),
                    generation_prompt=content_data.get('generation_prompt'),
                    generation_model=content_data.get('generation_model'),
                    generated_at=_parse_datetime_for_sqlite(content_data.get('generated_at')),
                    algorithm_case_id=new_case_id,
                    created_by_user_id=new_user_id,
                    created_at=_parse_datetime_for_sqlite(content_data.get('created_at')),
                )
                db.session.add(content)
                stats['tnm_calculator_content']['added'] += 1

        # Commit AJCC data
        try:
            db.session.commit()
            print(f"[IMPORT] AJCC data imported: {stats['ajcc_body_sections']['added']} sections, {stats['ajcc_disease_sites']['added']} diseases, {stats['ajcc_staging_data']['added']} staging entries, {stats['intelligent_tnm_data']['added']} intelligent TNM records, {stats.get('case_references', {}).get('added', 0)} case refs, {stats.get('case_reference_images', {}).get('added', 0)} case ref images, {stats.get('tnm_references', {}).get('added', 0)} TNM refs, {stats.get('anatomy_figures', {}).get('added', 0)} anatomy figs, {stats.get('tnm_images', {}).get('added', 0)} TNM images, {stats.get('case_image_stacks', {}).get('added', 0)} image stacks, {stats.get('case_image_annotations', {}).get('added', 0)} annotations, {stats.get('tnm_calculator_content', {}).get('added', 0)} TNM calculators")
        except Exception as ajcc_error:
            db.session.rollback()
            print(f"[IMPORT] ERROR during AJCC commit: {ajcc_error}")
        
        # ==================== IMPORT ASSOCIATION TABLES & NEW MODELS ====================

        # Import Related Cases links
        stats['related_cases_links'] = {'added': 0, 'skipped': 0}
        for link_data in backup_data.get('related_cases_links', []):
            if not isinstance(link_data, dict):
                continue
            old_case_id = link_data.get('case_id')
            old_related_id = link_data.get('related_case_id')
            new_case_id = case_id_map.get(old_case_id)
            new_related_id = case_id_map.get(old_related_id)
            if not new_case_id or not new_related_id:
                stats['related_cases_links']['skipped'] += 1
                continue
            # Check if link already exists
            existing = db.session.execute(
                related_cases.select().where(
                    (related_cases.c.case_id == new_case_id) &
                    (related_cases.c.related_case_id == new_related_id)
                )
            ).fetchone()
            if existing:
                stats['related_cases_links']['skipped'] += 1
                continue
            db.session.execute(related_cases.insert().values(
                case_id=new_case_id,
                related_case_id=new_related_id,
                relation_type=link_data.get('relation_type', 'related'),
            ))
            stats['related_cases_links']['added'] += 1

        # Import Case-Calculator Links
        stats['case_calculator_links_imported'] = {'added': 0, 'skipped': 0}
        # Build calculator ID map (slug -> new ID)
        calc_slug_map = {}
        for calc in TNMCalculatorContent.query.all():
            calc_slug_map[calc.slug] = calc.id
        for link_data in backup_data.get('case_calculator_links', []):
            if not isinstance(link_data, dict):
                continue
            old_case_id = link_data.get('case_id')
            old_calc_id = link_data.get('calculator_id')
            new_case_id = case_id_map.get(old_case_id)
            if not new_case_id or not old_calc_id:
                stats['case_calculator_links_imported']['skipped'] += 1
                continue
            # Calculator IDs should match directly (imported earlier)
            calc_exists = TNMCalculatorContent.query.get(old_calc_id)
            if not calc_exists:
                stats['case_calculator_links_imported']['skipped'] += 1
                continue
            existing = db.session.execute(
                case_calculator_links.select().where(
                    (case_calculator_links.c.case_id == new_case_id) &
                    (case_calculator_links.c.calculator_id == old_calc_id)
                )
            ).fetchone()
            if existing:
                stats['case_calculator_links_imported']['skipped'] += 1
                continue
            new_user_id = user_id_map.get(link_data.get('created_by_user_id')) if link_data.get('created_by_user_id') else None
            db.session.execute(case_calculator_links.insert().values(
                case_id=new_case_id,
                calculator_id=old_calc_id,
                created_by_user_id=new_user_id,
            ))
            stats['case_calculator_links_imported']['added'] += 1

        # Import Case-Reference Links
        stats['case_reference_links_imported'] = {'added': 0, 'skipped': 0}
        for link_data in backup_data.get('case_reference_links', []):
            if not isinstance(link_data, dict):
                continue
            old_case_id = link_data.get('case_id')
            old_ref_id = link_data.get('reference_id')
            new_case_id = case_id_map.get(old_case_id)
            if not new_case_id or not old_ref_id:
                stats['case_reference_links_imported']['skipped'] += 1
                continue
            ref_exists = CaseReference.query.get(old_ref_id)
            if not ref_exists:
                stats['case_reference_links_imported']['skipped'] += 1
                continue
            existing = db.session.execute(
                case_reference_links.select().where(
                    (case_reference_links.c.case_id == new_case_id) &
                    (case_reference_links.c.reference_id == old_ref_id)
                )
            ).fetchone()
            if existing:
                stats['case_reference_links_imported']['skipped'] += 1
                continue
            new_user_id = user_id_map.get(link_data.get('created_by_user_id')) if link_data.get('created_by_user_id') else None
            db.session.execute(case_reference_links.insert().values(
                case_id=new_case_id,
                reference_id=old_ref_id,
                created_by_user_id=new_user_id,
            ))
            stats['case_reference_links_imported']['added'] += 1

        # Import Case Audit Logs
        stats['case_audit_logs'] = {'added': 0, 'skipped': 0}
        if not is_frcr_examiner:
            for log_data in backup_data.get('case_audit_logs', []):
                if not isinstance(log_data, dict):
                    continue
                old_case_id = log_data.get('case_id')
                new_case_id = case_id_map.get(old_case_id)
                if not new_case_id:
                    stats['case_audit_logs']['skipped'] += 1
                    continue
                old_user_id = log_data.get('user_id')
                new_user_id = user_id_map.get(old_user_id) if old_user_id else None
                if not new_user_id:
                    stats['case_audit_logs']['skipped'] += 1
                    continue
                audit = CaseAuditLog(
                    case_id=new_case_id,
                    user_id=new_user_id,
                    action=log_data.get('action', ''),
                    changes=log_data.get('changes'),
                    notes=log_data.get('notes'),
                )
                if log_data.get('created_at'):
                    try:
                        audit.created_at = datetime.fromisoformat(log_data['created_at']) if isinstance(log_data['created_at'], str) else log_data['created_at']
                    except (ValueError, TypeError):
                        pass
                db.session.add(audit)
                stats['case_audit_logs']['added'] += 1

        # Import Case View Logs
        stats['case_view_logs'] = {'added': 0, 'skipped': 0}
        if not is_frcr_examiner:
            for vlog_data in backup_data.get('case_view_logs', []):
                if not isinstance(vlog_data, dict):
                    continue
                old_user_id = vlog_data.get('user_id')
                old_case_id = vlog_data.get('case_id')
                new_user_id = user_id_map.get(old_user_id) if old_user_id else None
                new_case_id = case_id_map.get(old_case_id) if old_case_id else None
                if not new_user_id or not new_case_id:
                    stats['case_view_logs']['skipped'] += 1
                    continue
                vlog = CaseViewLog(
                    user_id=new_user_id,
                    case_id=new_case_id,
                    time_spent_seconds=vlog_data.get('time_spent_seconds'),
                )
                if vlog_data.get('viewed_at'):
                    try:
                        vlog.viewed_at = datetime.fromisoformat(vlog_data['viewed_at']) if isinstance(vlog_data['viewed_at'], str) else vlog_data['viewed_at']
                    except (ValueError, TypeError):
                        pass
                db.session.add(vlog)
                stats['case_view_logs']['added'] += 1

        # Import Case Approval Queue
        stats['case_approval_queue'] = {'added': 0, 'skipped': 0}
        for entry_data in backup_data.get('case_approval_queue', []):
            if not isinstance(entry_data, dict):
                continue
            old_case_id = entry_data.get('case_id')
            new_case_id = case_id_map.get(old_case_id)
            if not new_case_id:
                stats['case_approval_queue']['skipped'] += 1
                continue
            # Check if already in queue
            existing = CaseApprovalQueue.query.filter_by(case_id=new_case_id).first()
            if existing:
                stats['case_approval_queue']['skipped'] += 1
                continue
            old_user_id = entry_data.get('submitted_by_user_id')
            new_user_id = user_id_map.get(old_user_id) if old_user_id else current_user.id
            entry = CaseApprovalQueue(
                case_id=new_case_id,
                submitted_by_user_id=new_user_id,
                admin_notes=entry_data.get('admin_notes'),
            )
            if entry_data.get('submitted_at'):
                try:
                    entry.submitted_at = datetime.fromisoformat(entry_data['submitted_at']) if isinstance(entry_data['submitted_at'], str) else entry_data['submitted_at']
                except (ValueError, TypeError):
                    pass
            db.session.add(entry)
            stats['case_approval_queue']['added'] += 1

        # Import User QA Progress (spaced repetition state)
        stats['user_qa_progress'] = {'added': 0, 'skipped': 0}
        if not is_frcr_examiner:
            for prog_data in backup_data.get('user_qa_progress', []):
                if not isinstance(prog_data, dict):
                    continue
                old_user_id = prog_data.get('user_id')
                new_user_id = user_id_map.get(old_user_id) if old_user_id else None
                if not new_user_id:
                    stats['user_qa_progress']['skipped'] += 1
                    continue
                # question_id mapping: questions were recreated with new IDs during case import
                # We need to match by case_id + question_number
                old_case_id = prog_data.get('case_id')
                new_case_id = case_id_map.get(old_case_id)
                if not new_case_id:
                    stats['user_qa_progress']['skipped'] += 1
                    continue
                old_question_id = prog_data.get('question_id')
                # Try to find matching question in the new case
                new_question = Question.query.filter_by(case_id=new_case_id).first()
                if not new_question:
                    stats['user_qa_progress']['skipped'] += 1
                    continue
                # Check for existing progress
                existing = UserQAProgress.query.filter_by(user_id=new_user_id, question_id=new_question.id).first()
                if existing:
                    stats['user_qa_progress']['skipped'] += 1
                    continue
                from datetime import date
                next_review = None
                if prog_data.get('next_review_date'):
                    try:
                        next_review = date.fromisoformat(prog_data['next_review_date']) if isinstance(prog_data['next_review_date'], str) else prog_data['next_review_date']
                    except (ValueError, TypeError):
                        next_review = date.today()
                else:
                    next_review = date.today()
                prog = UserQAProgress(
                    user_id=new_user_id,
                    question_id=new_question.id,
                    case_id=new_case_id,
                    ease_factor=prog_data.get('ease_factor', 2.5),
                    interval_days=prog_data.get('interval_days', 0),
                    repetition_number=prog_data.get('repetition_number', 0),
                    next_review_date=next_review,
                    times_correct=prog_data.get('times_correct', 0),
                    times_incorrect=prog_data.get('times_incorrect', 0),
                )
                if prog_data.get('last_reviewed_at'):
                    try:
                        prog.last_reviewed_at = datetime.fromisoformat(prog_data['last_reviewed_at']) if isinstance(prog_data['last_reviewed_at'], str) else prog_data['last_reviewed_at']
                    except (ValueError, TypeError):
                        pass
                db.session.add(prog)
                stats['user_qa_progress']['added'] += 1

        # Import AI Diagnosis Cache
        stats['ai_diagnosis_cache'] = {'added': 0, 'skipped': 0}
        for cache_data in backup_data.get('ai_diagnosis_cache', []):
            if not isinstance(cache_data, dict):
                continue
            diagnosis = cache_data.get('diagnosis')
            provider = cache_data.get('provider')
            model_name = cache_data.get('model_name')
            if not diagnosis or not provider or not model_name:
                stats['ai_diagnosis_cache']['skipped'] += 1
                continue
            existing = AiDiagnosisCache.query.filter_by(
                diagnosis=diagnosis, provider=provider, model_name=model_name
            ).first()
            if existing:
                stats['ai_diagnosis_cache']['skipped'] += 1
                continue
            old_case_id = cache_data.get('first_case_id')
            new_case_id = case_id_map.get(old_case_id) if old_case_id else None
            old_user_id = cache_data.get('first_user_id')
            new_user_id = user_id_map.get(old_user_id) if old_user_id else None
            if not new_case_id or not new_user_id:
                stats['ai_diagnosis_cache']['skipped'] += 1
                continue
            cache_entry = AiDiagnosisCache(
                diagnosis=diagnosis,
                provider=provider,
                model_name=model_name,
                first_case_id=new_case_id,
                first_user_id=new_user_id,
                query_count=cache_data.get('query_count', 1),
            )
            if cache_data.get('first_generated_at'):
                try:
                    cache_entry.first_generated_at = datetime.fromisoformat(cache_data['first_generated_at']) if isinstance(cache_data['first_generated_at'], str) else cache_data['first_generated_at']
                except (ValueError, TypeError):
                    pass
            if cache_data.get('last_queried_at'):
                try:
                    cache_entry.last_queried_at = datetime.fromisoformat(cache_data['last_queried_at']) if isinstance(cache_data['last_queried_at'], str) else cache_data['last_queried_at']
                except (ValueError, TypeError):
                    pass
            db.session.add(cache_entry)
            stats['ai_diagnosis_cache']['added'] += 1

        # Import AI Prelim Case Data (audit trail)
        stats['ai_prelim_case_data'] = {'added': 0, 'skipped': 0}
        for apcd_data in backup_data.get('ai_prelim_case_data', []):
            if not isinstance(apcd_data, dict):
                continue
            old_case_id = apcd_data.get('case_id')
            new_case_id = case_id_map.get(old_case_id) if old_case_id else None
            if not new_case_id:
                stats['ai_prelim_case_data']['skipped'] += 1
                continue
            old_user_id = apcd_data.get('created_by_user_id')
            new_user_id = user_id_map.get(old_user_id) if old_user_id else None
            entry = AiPrelimCaseData(
                case_id=new_case_id,
                created_by_user_id=new_user_id,
                provider=apcd_data.get('provider', ''),
                model_name=apcd_data.get('model_name', ''),
                prompt_version=apcd_data.get('prompt_version', ''),
                request_payload=apcd_data.get('request_payload'),
                response_payload=apcd_data.get('response_payload'),
            )
            if apcd_data.get('created_at'):
                entry.created_at = _parse_datetime_for_sqlite(apcd_data['created_at']) or datetime.utcnow()
            db.session.add(entry)
            stats['ai_prelim_case_data']['added'] += 1

        # Import Clinical Protocols
        stats['clinical_protocols'] = {'added': 0, 'skipped': 0}
        protocol_id_map = {}
        for proto_data in backup_data.get('clinical_protocols', []):
            if not isinstance(proto_data, dict):
                continue
            title = proto_data.get('title', '')
            category = proto_data.get('category', '')
            if not title or not category:
                stats['clinical_protocols']['skipped'] += 1
                continue
            existing = ClinicalProtocol.query.filter_by(title=title, category=category).first()
            if existing:
                protocol_id_map[proto_data.get('id')] = existing.id
                stats['clinical_protocols']['skipped'] += 1
                continue
            old_created_by = proto_data.get('created_by_user_id')
            old_verified_by = proto_data.get('verified_by_user_id')
            protocol = ClinicalProtocol(
                category=category,
                title=title,
                keywords=proto_data.get('keywords', title),
                content_structured=proto_data.get('content_structured'),
                content_html=proto_data.get('content_html'),
                source_citation=proto_data.get('source_citation', ''),
                guideline_version=proto_data.get('guideline_version'),
                source_url=proto_data.get('source_url'),
                is_published=proto_data.get('is_published', False),
                verified_by_user_id=user_id_map.get(old_verified_by) if old_verified_by else None,
                verified_at=_parse_datetime_for_sqlite(proto_data.get('verified_at')),
                created_by_user_id=user_id_map.get(old_created_by) if old_created_by else None,
            )
            if proto_data.get('created_at'):
                protocol.created_at = _parse_datetime_for_sqlite(proto_data['created_at']) or datetime.utcnow()
            if proto_data.get('updated_at'):
                protocol.updated_at = _parse_datetime_for_sqlite(proto_data['updated_at']) or datetime.utcnow()
            db.session.add(protocol)
            db.session.flush()
            protocol_id_map[proto_data.get('id')] = protocol.id
            stats['clinical_protocols']['added'] += 1

        # Import On-Call Query Logs
        stats['oncall_query_logs'] = {'added': 0, 'skipped': 0}
        for log_data in backup_data.get('oncall_query_logs', []):
            if not isinstance(log_data, dict):
                continue
            old_user_id = log_data.get('user_id')
            new_user_id = user_id_map.get(old_user_id) if old_user_id else None
            if not new_user_id:
                stats['oncall_query_logs']['skipped'] += 1
                continue
            log_entry = OnCallQueryLog(
                user_id=new_user_id,
                query_text=log_data.get('query_text', ''),
                matched_protocol_ids=log_data.get('matched_protocol_ids'),
                ai_response_text=log_data.get('ai_response_text'),
                model_used=log_data.get('model_used'),
                token_count=log_data.get('token_count'),
                response_source=log_data.get('response_source', 'protocol'),
            )
            if log_data.get('created_at'):
                log_entry.created_at = _parse_datetime_for_sqlite(log_data['created_at']) or datetime.utcnow()
            db.session.add(log_entry)
            stats['oncall_query_logs']['added'] += 1

        # Import Reporting Templates
        stats['reporting_templates'] = {'added': 0, 'skipped': 0}
        for rt_data in backup_data.get('reporting_templates', []):
            if not isinstance(rt_data, dict):
                continue
            slug = rt_data.get('slug', '')
            if not slug:
                stats['reporting_templates']['skipped'] += 1
                continue
            existing = ReportingTemplate.query.filter_by(slug=slug).first()
            if existing:
                stats['reporting_templates']['skipped'] += 1
                continue
            old_created_by = rt_data.get('created_by_user_id')
            old_verified_by = rt_data.get('verified_by_user_id')
            rt = ReportingTemplate(
                slug=slug,
                title=rt_data.get('title', ''),
                category=rt_data.get('category', ''),
                body_section=rt_data.get('body_section'),
                description=rt_data.get('description'),
                keywords=rt_data.get('keywords'),
                template_html=rt_data.get('template_html'),
                algorithm_html=rt_data.get('algorithm_html'),
                source_citation=rt_data.get('source_citation'),
                guideline_version=rt_data.get('guideline_version'),
                is_available=rt_data.get('is_available', False),
                is_ai_generated=rt_data.get('is_ai_generated', False),
                verified_by_user_id=user_id_map.get(old_verified_by) if old_verified_by else None,
                verified_at=_parse_datetime_for_sqlite(rt_data.get('verified_at')),
                pacs_report_text=rt_data.get('pacs_report_text'),
                generation_prompt=rt_data.get('generation_prompt'),
                generation_model=rt_data.get('generation_model'),
                generated_at=_parse_datetime_for_sqlite(rt_data.get('generated_at')),
                created_by_user_id=user_id_map.get(old_created_by) if old_created_by else None,
                last_edit_note=rt_data.get('last_edit_note'),
            )
            if rt_data.get('created_at'):
                rt.created_at = _parse_datetime_for_sqlite(rt_data['created_at']) or datetime.utcnow()
            if rt_data.get('updated_at'):
                rt.updated_at = _parse_datetime_for_sqlite(rt_data['updated_at']) or datetime.utcnow()
            db.session.add(rt)
            stats['reporting_templates']['added'] += 1

        # Import Incidental Finding Calculators
        stats['incidental_finding_calculators'] = {'added': 0, 'skipped': 0}
        for ifc_data in backup_data.get('incidental_finding_calculators', []):
            if not isinstance(ifc_data, dict):
                continue
            slug = ifc_data.get('slug', '')
            if not slug:
                stats['incidental_finding_calculators']['skipped'] += 1
                continue
            existing = IncidentalFindingCalculator.query.filter_by(slug=slug).first()
            if existing:
                stats['incidental_finding_calculators']['skipped'] += 1
                continue
            old_created_by = ifc_data.get('created_by_user_id')
            old_verified_by = ifc_data.get('verified_by_user_id')
            ifc = IncidentalFindingCalculator(
                slug=slug,
                finding_name=ifc_data.get('finding_name', ''),
                body_section=ifc_data.get('body_section'),
                category=ifc_data.get('category'),
                description=ifc_data.get('description'),
                keywords=ifc_data.get('keywords'),
                calculator_html=ifc_data.get('calculator_html'),
                algorithm_html=ifc_data.get('algorithm_html'),
                guideline_source=ifc_data.get('guideline_source'),
                guideline_version=ifc_data.get('guideline_version'),
                guideline_url=ifc_data.get('guideline_url'),
                is_available=ifc_data.get('is_available', False),
                generation_prompt=ifc_data.get('generation_prompt'),
                generation_model=ifc_data.get('generation_model'),
                generated_at=_parse_datetime_for_sqlite(ifc_data.get('generated_at')),
                verified_by_user_id=user_id_map.get(old_verified_by) if old_verified_by else None,
                verified_at=_parse_datetime_for_sqlite(ifc_data.get('verified_at')),
                created_by_user_id=user_id_map.get(old_created_by) if old_created_by else None,
                last_edit_note=ifc_data.get('last_edit_note'),
            )
            if ifc_data.get('created_at'):
                ifc.created_at = _parse_datetime_for_sqlite(ifc_data['created_at']) or datetime.utcnow()
            if ifc_data.get('updated_at'):
                ifc.updated_at = _parse_datetime_for_sqlite(ifc_data['updated_at']) or datetime.utcnow()
            db.session.add(ifc)
            stats['incidental_finding_calculators']['added'] += 1

        # Final commit for new tables
        try:
            db.session.commit()
            print(f"[IMPORT] New tables imported: {stats.get('related_cases_links', {}).get('added', 0)} related links, {stats.get('case_audit_logs', {}).get('added', 0)} audit logs, {stats.get('case_view_logs', {}).get('added', 0)} view logs, {stats.get('user_qa_progress', {}).get('added', 0)} QA progress, {stats.get('ai_diagnosis_cache', {}).get('added', 0)} AI cache, {stats.get('clinical_protocols', {}).get('added', 0)} protocols, {stats.get('reporting_templates', {}).get('added', 0)} reporting templates, {stats.get('incidental_finding_calculators', {}).get('added', 0)} IF calculators")
        except Exception as new_tables_error:
            db.session.rollback()
            print(f"[IMPORT] ERROR during new tables commit: {new_tables_error}")

        # Build response message
        message_parts = ['Database imported successfully']
        if stats['staging']['added'] > 0:
            staging_msg = f"{stats['staging']['added']} case(s) sent to staging for review (missing critical fields)."
            if stats['staging']['images_stored'] > 0:
                staging_msg += f" {stats['staging']['images_stored']} image(s) stored in staging cases."
            message_parts.append(staging_msg)
        
        # Include debug info about image matching in response
        debug_info = {
            'total_images_in_backup': len(backup_data.get('case_images', [])),
            'staging_cases_with_images': stats['staging']['images_stored'],
            'staging_cases_total': stats['staging']['added'],
        }
        
        return jsonify({
            'success': True,
            'message': ' '.join(message_parts),
            'stats': stats,
            'staging_count': stats['staging']['added'],
            'staging_images_count': stats['staging']['images_stored'],
            'import_batch_id': import_batch_id if stats['staging']['added'] > 0 else None,
            'debug': debug_info
        })
        
    except Exception as e:
        db.session.rollback()
        import traceback
        error_traceback = traceback.format_exc()
        error_message = str(e)
        error_lower = error_message.lower()
        
        # Handle PostgreSQL specific errors
        # Check for actual PostgreSQL error codes and messages
        if hasattr(e, 'orig') and hasattr(e.orig, 'pgcode'):
            # PostgreSQL specific error
            pgcode = e.orig.pgcode
            if pgcode == '40001':  # Serialization failure
                error_message = 'Database transaction conflict. Please try again in a few moments.'
            elif pgcode == '40P01':  # Deadlock detected
                error_message = 'Database deadlock detected. Please try again.'
            elif pgcode == '23505':  # Unique violation
                error_message = 'Duplicate entry detected. Some data may already exist in the database.'
            elif pgcode == '23503':  # Foreign key violation
                error_message = 'Data integrity error. The backup file may contain invalid references.'
            elif pgcode == '23502':  # Not null violation
                error_message = 'Missing required data. The backup file may be incomplete.'
        
        # Fallback to string matching
        if 'timeout' in error_lower or 'connection' in error_lower or 'timed out' in error_lower:
            error_message = 'Database connection timeout. The import operation may be too large or taking too long. Please try importing in smaller batches or contact support.'
        elif 'deadlock' in error_lower or ('lock' in error_lower and 'waiting' in error_lower):
            error_message = 'Database transaction conflict. Another operation may be in progress. Please try again in a few moments.'
        elif 'disturbed' in error_lower or 'body' in error_lower or 'request entity too large' in error_lower:
            # This might be a request body size issue or connection issue
            error_message = 'Request body error. The backup file may be too large (Vercel limit: 4.5MB) or the connection was interrupted. Please try a smaller backup file or split the import.'
        elif 'violates' in error_lower and 'constraint' in error_lower:
            error_message = 'Data integrity error. The backup file may contain invalid data or duplicate entries. Please verify the backup file.'
        elif 'syntax error' in error_lower or 'invalid' in error_lower or 'malformed' in error_lower:
            error_message = 'Invalid data format. Please ensure the backup file is valid JSON and was exported from a compatible version.'
        elif 'operationalerror' in error_lower or 'database' in error_lower:
            error_message = f'Database error: {str(e)[:200]}. Please check Vercel logs for details.'
        
        print(f"[IMPORT] ERROR: {error_message}")
        print(f"[IMPORT] Original error: {str(e)}")
        print(f"[IMPORT] TRACEBACK:\n{error_traceback}")
        # Log to stderr for Vercel logs
        import sys
        sys.stderr.write(f"[IMPORT] ERROR: {error_message}\n")
        sys.stderr.write(f"[IMPORT] Original: {str(e)}\n")
        sys.stderr.write(f"[IMPORT] TRACEBACK:\n{error_traceback}\n")
        return jsonify({
            'error': f'Import failed: {error_message}',
            'details': error_traceback.split('\n')[-5:] if len(error_traceback) > 0 else []
        }), 500


@backup_bp.route('/status', methods=['GET'])
@login_required
def backup_status():
    """Get backup status and reminder info"""
    if not check_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    last_backup = session.get('last_backup_time')
    
    if last_backup:
        last_backup_dt = datetime.fromisoformat(last_backup)
        hours_since = (datetime.utcnow() - last_backup_dt).total_seconds() / 3600
        needs_backup = hours_since >= 24
    else:
        needs_backup = True
        hours_since = None
    
    # Count records
    stats = {
        'total_users': User.query.count(),
        'total_cases': Case.query.count(),
        'total_questions': Question.query.count(),
        'total_answers': Answer.query.count(),
        'total_images': CaseImage.query.count(),
        'total_sessions': RevisionSession.query.count(),
        'total_flags': CaseFlag.query.count(),
        # AJCC TNM stats
        'ajcc_body_sections': AJCCBodySection.query.count(),
        'ajcc_disease_sites': AJCCDiseaseSite.query.count(),
        'ajcc_diagnosis_years': AJCCDiagnosisYear.query.count(),
        'ajcc_staging_data': AJCCStagingData.query.count(),
        'ajcc_disease_mappings': AJCCDiseaseMapping.query.count(),
        'intelligent_tnm_data': IntelligentTNMData.query.count(),
        'case_reference_images': CaseReferenceImage.query.count(),
        # Clinical Tools
        'clinical_protocols': ClinicalProtocol.query.count(),
        'oncall_query_logs': OnCallQueryLog.query.count(),
        'reporting_templates': ReportingTemplate.query.count(),
        'incidental_finding_calculators': IncidentalFindingCalculator.query.count(),
    }
    
    return jsonify({
        'is_admin': True,
        'last_backup_time': last_backup,
        'hours_since_backup': hours_since,
        'needs_backup': needs_backup,
        'stats': stats
    })