"""
Database Backup and Restore Routes for Web Deployment
Handles manual backup downloads and restore from uploads
"""
from flask import Blueprint, jsonify, send_file, request, session, render_template
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
    ClinicalProtocol, OnCallQueryLog,
    RadiologyTemplate, ReportingAlgorithm,
    IncidentalFindingCalculator,
    # AI audit trail
    AIAuditLog,
    # Content requests
    ContentRequest,
    # Radiology pearls
    RadiologyPearl,
    # Knowledge linking tables
    case_algorithm_links, case_template_links, case_pearl_links,
    # Vetting
    VettingSession, VettingAlgorithm,
    # Admin docs and memory sync
    AdminDocument, ClaudeMemoryUpdate, TourCapture,
    # Peer review / CMV
    PeerReviewClaim, PeerReviewFlag, ManualVerification,
    # RadIQ
    RadIQQuery, RadIQFeedback,
    # Smart Reporter sessions
    ReportingSession, PublishedReport,
    # Learning module
    LearningQuestion, LearningQuestionProgress, LearningQuestionReference,
    # Content intelligence
    ContentIntelligence, UserGeneratedIntelligence,
    # Snippet media
    SnippetReference, SnippetDocument, SnippetImage,
    # MDT module
    MdtMeeting, MdtCase,
    # Audit and compliance
    PiiOverrideLog, RateLimitEntry, ErasureLog, AdminActionLog,
    # OSCE Guide
    OsceCase, OsceCaseImage,
    # Additional association tables
    case_learning_links, content_links,
)
from datetime import datetime
from sqlalchemy import inspect
import json
import io
import os
import uuid

backup_bp = Blueprint('backup', __name__, url_prefix='/api/backup')


@backup_bp.route('/manager', methods=['GET'])
@login_required
def backup_manager_page():
    """Serve the standalone backup manager page"""
    if not check_admin():
        return jsonify({'error': 'Admin access required'}), 403
    return render_template('backup_manager.html')


def _sanitize_backup_data(backup_data):
    """Sanitize all backup records for SQLite compatibility.
    1. Convert dict values to JSON strings (SQLite Text columns reject Python dicts)
    2. Convert ISO datetime strings to Python datetime objects (SQLite DateTime
       columns reject strings; PostgreSQL silently handles both)
    Must run AFTER json.loads() but BEFORE any import loops."""
    import re
    # Match ISO 8601 datetime: 2026-02-06T20:10:33 with optional fractional seconds and timezone
    _iso_re = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')
    for key, records in backup_data.items():
        if isinstance(records, list):
            for record in records:
                if isinstance(record, dict):
                    for field, val in record.items():
                        if isinstance(val, dict):
                            record[field] = json.dumps(val)
                        elif isinstance(val, str) and _iso_re.match(val) and (
                            field.endswith('_at') or field.endswith('_date') or field == 'last_login'
                        ):
                            try:
                                s = val.replace('Z', '+00:00')
                                dt = datetime.fromisoformat(s)
                                record[field] = dt.replace(tzinfo=None) if dt.tzinfo else dt
                            except (ValueError, TypeError):
                                pass


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

def _build_backup_data():
    """Build the complete backup data dict. Shared by download and scheduled backup."""
    backup_data = {
        'metadata': {
            'backup_date': datetime.utcnow().isoformat(),
            'database_type': 'postgresql' if os.getenv('DATABASE_URL') or os.getenv('DATABASE_POSTGRES_URL_NON_POOLING') else 'sqlite',
            'version': '3.0',  # Bumped for 27 new models (protocols, vetting, CMV, MDT, etc.)
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
        'reporting_templates': [],  # Legacy — kept for backward compat
        'radiology_templates': [],
        'reporting_algorithms': [],
        'incidental_finding_calculators': [],
        # AI audit trail
        'ai_audit_logs': [],
        # Content requests
        'content_requests': [],
        # Radiology pearls
        'radiology_pearls': [],
        # Import staging
        'imported_case_staging': [],
        # Vetting
        'vetting_sessions': [],
        'vetting_algorithms': [],
        # Admin docs and memory sync
        'admin_documents': [],
        'claude_memory_updates': [],
        'tour_captures': [],
        # Peer review / CMV
        'peer_review_claims': [],
        'peer_review_flags': [],
        'manual_verifications': [],
        # RadIQ
        'radiq_queries': [],
        'radiq_feedback': [],
        # Smart Reporter sessions
        'reporting_sessions': [],
        'published_reports': [],
        # Learning module
        'learning_questions': [],
        'learning_question_progress': [],
        'learning_question_references': [],
        # Content intelligence
        'content_intelligence': [],
        'user_generated_intelligence': [],
        # Snippet media
        'snippet_references': [],
        'snippet_documents': [],
        'snippet_images': [],
        # MDT module
        'mdt_meetings': [],
        'mdt_cases': [],
        # OSCE Guide
        'osce_cases': [],
        'osce_case_images': [],
        # Audit and compliance
        'pii_override_logs': [],
        'rate_limit_entries': [],
        'erasure_logs': [],
        'admin_action_logs': [],
        # Additional association tables
        'case_learning_links': [],
        'content_links': [],
    }
    
    # Export users (with password hashes for sync purposes)
    # SECURITY: Intentionally excludes recovery_token, notion_access_token,
    # anki_api_key, sciencedirect_session_cookies to prevent credential leakage
    for user in User.query.all():
        user_data = {
            'id': user.id,  # Include ID for proper mapping
            'email': user.email,
            'password_hash': user.password_hash,  # Salted hash, needed for DB sync
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

    # Export Radiology Templates (plain-text PACS reports)
    for rt in RadiologyTemplate.query.all():
        backup_data['radiology_templates'].append({
            'id': rt.id, 'slug': rt.slug, 'title': rt.title,
            'origin': rt.origin, 'category': rt.category,
            'body_section': rt.body_section, 'description': rt.description,
            'keywords': rt.keywords, 'template_text': rt.template_text,
            'source_citation': rt.source_citation, 'guideline_version': rt.guideline_version,
            'is_available': rt.is_available, 'is_ai_generated': rt.is_ai_generated,
            'verified_by_user_id': rt.verified_by_user_id,
            'verified_at': rt.verified_at.isoformat() if rt.verified_at else None,
            'generation_prompt': rt.generation_prompt, 'generation_model': rt.generation_model,
            'generated_at': rt.generated_at.isoformat() if rt.generated_at else None,
            'created_by_user_id': rt.created_by_user_id,
            'last_edit_note': rt.last_edit_note,
            'created_at': rt.created_at.isoformat() if rt.created_at else None,
            'updated_at': rt.updated_at.isoformat() if rt.updated_at else None,
        })

    # Export Reporting Algorithms (interactive decision trees)
    for ra in ReportingAlgorithm.query.all():
        backup_data['reporting_algorithms'].append({
            'id': ra.id, 'slug': ra.slug, 'title': ra.title,
            'origin': ra.origin, 'category': ra.category,
            'body_section': ra.body_section, 'description': ra.description,
            'keywords': ra.keywords,
            'template_html': ra.template_html, 'algorithm_html': ra.algorithm_html,
            'source_citation': ra.source_citation, 'guideline_version': ra.guideline_version,
            'is_available': ra.is_available, 'is_ai_generated': ra.is_ai_generated,
            'verified_by_user_id': ra.verified_by_user_id,
            'verified_at': ra.verified_at.isoformat() if ra.verified_at else None,
            'generation_prompt': ra.generation_prompt, 'generation_model': ra.generation_model,
            'generated_at': ra.generated_at.isoformat() if ra.generated_at else None,
            'created_by_user_id': ra.created_by_user_id,
            'last_edit_note': ra.last_edit_note,
            'created_at': ra.created_at.isoformat() if ra.created_at else None,
            'updated_at': ra.updated_at.isoformat() if ra.updated_at else None,
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

    # Export AI audit logs
    for log in AIAuditLog.query.order_by(AIAuditLog.created_at.desc()).all():
        backup_data['ai_audit_logs'].append(log.to_dict())

    # Export Content Requests
    for cr in ContentRequest.query.all():
        backup_data['content_requests'].append({
            'id': cr.id,
            'user_id': cr.user_id,
            'request_type': cr.request_type,
            'title': cr.title,
            'description': cr.description,
            'body_section': cr.body_section,
            'status': cr.status,
            'admin_notes': cr.admin_notes,
            'created_at': cr.created_at.isoformat() if cr.created_at else None,
        })

    # Export Radiology Pearls
    for pearl in RadiologyPearl.query.all():
        backup_data['radiology_pearls'].append({
            'id': pearl.id,
            'content_hash': pearl.content_hash,
            'pearl_text': pearl.pearl_text,
            'body_section': pearl.body_section,
            'modality': pearl.modality,
            'tags': pearl.tags,
            'source_report_context': pearl.source_report_context,
            'is_verified': pearl.is_verified,
            'created_by_user_id': pearl.created_by_user_id,
            'verified_by_user_id': pearl.verified_by_user_id,
            'verified_at': pearl.verified_at.isoformat() if pearl.verified_at else None,
            'created_at': pearl.created_at.isoformat() if pearl.created_at else None,
            'updated_at': pearl.updated_at.isoformat() if pearl.updated_at else None,
        })

    # Export Imported Case Staging
    for ics in ImportedCaseStaging.query.all():
        backup_data['imported_case_staging'].append({
            'id': ics.id,
            'original_id': ics.original_id,
            'case_number': ics.case_number,
            'diagnosis': ics.diagnosis,
            'questions': ics.questions,
            'answers': ics.answers,
            'discussion': ics.discussion,
            'module': ics.module.value if ics.module else None,
            'body_part': ics.body_part.value if ics.body_part else None,
            'age_group': ics.age_group.value if ics.age_group else None,
            'is_public': ics.is_public,
            'enrichment_status': ics.enrichment_status,
            'enriched_by_user_id': ics.enriched_by_user_id,
            'enriched_at': ics.enriched_at.isoformat() if ics.enriched_at else None,
            'enrichment_notes': ics.enrichment_notes,
            'approved_by_user_id': ics.approved_by_user_id,
            'approved_at': ics.approved_at.isoformat() if ics.approved_at else None,
            'approval_notes': ics.approval_notes,
            'promoted_to_case_id': ics.promoted_to_case_id,
            'promoted_at': ics.promoted_at.isoformat() if ics.promoted_at else None,
            'previous_staging_id': ics.previous_staging_id,
            'is_replacement': ics.is_replacement,
            'import_batch_id': ics.import_batch_id,
            'source_system': ics.source_system,
            'import_timestamp': ics.import_timestamp.isoformat() if ics.import_timestamp else None,
            'created_at': ics.created_at.isoformat() if ics.created_at else None,
            'updated_at': ics.updated_at.isoformat() if ics.updated_at else None,
        })

    # ==================== VETTING ====================

    for vs in VettingSession.query.all():
        backup_data['vetting_sessions'].append({
            'id': vs.id, 'user_id': vs.user_id,
            'raw_clinical_text': vs.raw_clinical_text,
            'modality_hint': vs.modality_hint,
            'cleaned_clinical_text': vs.cleaned_clinical_text,
            'study_type': vs.study_type,
            'safety_checks_json': vs.safety_checks_json,
            'protocol_source': vs.protocol_source,
            'protocol_id': vs.protocol_id,
            'final_clinical_details': vs.final_clinical_details,
            'final_shorthand': vs.final_shorthand,
            'final_detailed_html': vs.final_detailed_html,
            'final_special_notes': vs.final_special_notes,
            'ai_model': vs.ai_model,
            'ai_tokens_used': vs.ai_tokens_used,
            'created_at': vs.created_at.isoformat() if vs.created_at else None,
        })

    for va in VettingAlgorithm.query.all():
        backup_data['vetting_algorithms'].append({
            'id': va.id, 'algorithm_key': va.algorithm_key,
            'title': va.title, 'slug': va.slug,
            'body_section': va.body_section,
            'clinical_scenario': va.clinical_scenario,
            'entry_criteria_json': va.entry_criteria_json,
            'steps_json': va.steps_json,
            'safety_json': va.safety_json,
            'tags': va.tags, 'keywords': va.keywords,
            'origin': va.origin,
            'is_published': va.is_published,
            'is_verified': va.is_verified,
            'verified_by_user_id': va.verified_by_user_id,
            'verified_at': va.verified_at.isoformat() if va.verified_at else None,
            'created_at': va.created_at.isoformat() if va.created_at else None,
            'updated_at': va.updated_at.isoformat() if va.updated_at else None,
        })

    # ==================== ADMIN DOCS & MEMORY SYNC ====================

    for doc in AdminDocument.query.all():
        backup_data['admin_documents'].append({
            'id': doc.id, 'slug': doc.slug, 'title': doc.title,
            'category': doc.category,
            'content_html': doc.content_html,
            'last_edited_by': doc.last_edited_by,
            'created_at': doc.created_at.isoformat() if doc.created_at else None,
            'updated_at': doc.updated_at.isoformat() if doc.updated_at else None,
        })

    for cmu in ClaudeMemoryUpdate.query.all():
        backup_data['claude_memory_updates'].append({
            'id': cmu.id, 'category': cmu.category,
            'summary': cmu.summary, 'details': cmu.details,
            'source_doc_slug': cmu.source_doc_slug,
            'created_by': cmu.created_by,
            'created_at': cmu.created_at.isoformat() if cmu.created_at else None,
            'is_synced': cmu.is_synced,
            'synced_at': cmu.synced_at.isoformat() if cmu.synced_at else None,
        })

    for tc in TourCapture.query.all():
        backup_data['tour_captures'].append({
            'id': tc.id, 'tour_name': tc.tour_name,
            'step_number': tc.step_number,
            'step_label': tc.step_label,
            'user_input': tc.user_input,
            'response_json': tc.response_json,
            'notes': tc.notes,
            'screenshot_url': tc.screenshot_url,
            'created_at': tc.created_at.isoformat() if tc.created_at else None,
        })

    # ==================== PEER REVIEW / CMV ====================

    for prc in PeerReviewClaim.query.all():
        backup_data['peer_review_claims'].append({
            'id': prc.id, 'content_type': prc.content_type,
            'content_id': prc.content_id,
            'claim_text': prc.claim_text, 'claim_type': prc.claim_type,
            'gemini_verdict': prc.gemini_verdict,
            'gemini_confidence': prc.gemini_confidence,
            'gemini_reasoning': prc.gemini_reasoning,
            'gemini_correction': prc.gemini_correction,
            'gemini_model': prc.gemini_model,
            'admin_override': prc.admin_override,
            'admin_notes': prc.admin_notes,
            'admin_reference_url': prc.admin_reference_url,
            'admin_reference_title': prc.admin_reference_title,
            'reviewed_by_admin_id': prc.reviewed_by_admin_id,
            'reviewed_at': prc.reviewed_at.isoformat() if prc.reviewed_at else None,
            'context_body_section': prc.context_body_section,
            'context_modality': prc.context_modality,
            'context_topic': prc.context_topic,
            'created_at': prc.created_at.isoformat() if prc.created_at else None,
        })

    for prf in PeerReviewFlag.query.all():
        backup_data['peer_review_flags'].append({
            'id': prf.id, 'user_id': prf.user_id,
            'content_type': prf.content_type, 'content_id': prf.content_id,
            'section': prf.section, 'details': prf.details,
            'claim_text': prf.claim_text, 'selected_text': prf.selected_text,
            'error_type': prf.error_type, 'severity': prf.severity,
            'page_url': prf.page_url,
            'is_resolved': prf.is_resolved,
            'resolved_by_user_id': prf.resolved_by_user_id,
            'resolved_at': prf.resolved_at.isoformat() if prf.resolved_at else None,
            'resolution_notes': prf.resolution_notes,
            'created_at': prf.created_at.isoformat() if prf.created_at else None,
        })

    for mv in ManualVerification.query.all():
        backup_data['manual_verifications'].append({
            'id': mv.id, 'content_type': mv.content_type,
            'content_id': mv.content_id,
            'selected_text': mv.selected_text, 'custom_label': mv.custom_label,
            'pubmed_doi': mv.pubmed_doi, 'pubmed_pmid': mv.pubmed_pmid,
            'pubmed_title': mv.pubmed_title, 'pubmed_authors': mv.pubmed_authors,
            'pubmed_journal': mv.pubmed_journal, 'pubmed_year': mv.pubmed_year,
            'verified_by_user_id': mv.verified_by_user_id,
            'created_at': mv.created_at.isoformat() if mv.created_at else None,
        })

    # ==================== RADIQ ====================

    for rq in RadIQQuery.query.all():
        backup_data['radiq_queries'].append({
            'id': rq.id, 'user_id': rq.user_id,
            'category': rq.category, 'question': rq.question,
            'response_text': rq.response_text,
            'created_at': rq.created_at.isoformat() if rq.created_at else None,
        })

    for rf in db.session.query(RadIQFeedback).all():
        backup_data['radiq_feedback'].append({
            'id': rf.id, 'query_id': rf.query_id,
            'user_id': rf.user_id, 'reason': rf.reason,
            'details': rf.details, 'is_resolved': rf.is_resolved,
            'resolved_by_user_id': rf.resolved_by_user_id,
            'resolved_at': rf.resolved_at.isoformat() if rf.resolved_at else None,
            'resolution_notes': rf.resolution_notes,
            'created_at': rf.created_at.isoformat() if rf.created_at else None,
        })

    # ==================== SMART REPORTER SESSIONS ====================

    for rs in ReportingSession.query.all():
        backup_data['reporting_sessions'].append({
            'id': rs.id, 'user_id': rs.user_id,
            'clinical_question': rs.clinical_question,
            'modality': rs.modality, 'body_section': rs.body_section,
            'algorithm_tree_json': rs.algorithm_tree_json,
            'walkthrough_answers_json': rs.walkthrough_answers_json,
            'report_text': rs.report_text,
            'status': rs.status, 'provider': rs.provider,
            'model_name': rs.model_name,
            'generation_tokens': rs.generation_tokens,
            'ask_claude_count': rs.ask_claude_count,
            'created_at': rs.created_at.isoformat() if rs.created_at else None,
            'completed_at': rs.completed_at.isoformat() if rs.completed_at else None,
            'updated_at': rs.updated_at.isoformat() if rs.updated_at else None,
        })

    for pr in PublishedReport.query.all():
        backup_data['published_reports'].append({
            'id': pr.id, 'session_id': pr.session_id,
            'user_id': pr.user_id,
            'clinical_question': pr.clinical_question,
            'modality': pr.modality, 'body_section': pr.body_section,
            'report_text': pr.report_text,
            'algorithm_tree_json': pr.algorithm_tree_json,
            'contributor_name': pr.contributor_name,
            'published_at': pr.published_at.isoformat() if pr.published_at else None,
        })

    # ==================== LEARNING MODULE ====================

    for lq in LearningQuestion.query.all():
        backup_data['learning_questions'].append({
            'id': lq.id, 'question_type': lq.question_type,
            'body_section': lq.body_section, 'modality': lq.modality,
            'module': lq.module, 'title': lq.title,
            'html_content': lq.html_content,
            'source_report_context': lq.source_report_context,
            'tags': lq.tags, 'search_tags': lq.search_tags,
            'description': lq.description,
            'content_hash': lq.content_hash,
            'created_by_user_id': lq.created_by_user_id,
            'created_at': lq.created_at.isoformat() if lq.created_at else None,
        })

    for lqp in LearningQuestionProgress.query.all():
        backup_data['learning_question_progress'].append({
            'id': lqp.id, 'user_id': lqp.user_id,
            'learning_question_id': lqp.learning_question_id,
            'score': lqp.score, 'best_score': lqp.best_score,
            'times_attempted': lqp.times_attempted,
            'last_attempted_at': lqp.last_attempted_at.isoformat() if lqp.last_attempted_at else None,
            'created_at': lqp.created_at.isoformat() if lqp.created_at else None,
        })

    for lqr in LearningQuestionReference.query.all():
        backup_data['learning_question_references'].append({
            'id': lqr.id, 'learning_question_id': lqr.learning_question_id,
            'ref_number': lqr.ref_number, 'title': lqr.title,
            'url': lqr.url, 'journal': lqr.journal, 'year': lqr.year,
            'created_at': lqr.created_at.isoformat() if lqr.created_at else None,
        })

    # ==================== CONTENT INTELLIGENCE ====================

    for ci in ContentIntelligence.query.all():
        backup_data['content_intelligence'].append({
            'id': ci.id, 'content_type': ci.content_type,
            'content_id': ci.content_id, 'summary': ci.summary,
            'search_tags': ci.search_tags,
            'cross_links_json': ci.cross_links_json,
            'processing_model': ci.processing_model,
            'processing_tokens': ci.processing_tokens,
            'processed_at': ci.processed_at.isoformat() if ci.processed_at else None,
            'is_verified': ci.is_verified,
            'verified_by_user_id': ci.verified_by_user_id,
            'verified_at': ci.verified_at.isoformat() if ci.verified_at else None,
            'created_at': ci.created_at.isoformat() if ci.created_at else None,
            'updated_at': ci.updated_at.isoformat() if ci.updated_at else None,
        })

    for ugi in UserGeneratedIntelligence.query.all():
        backup_data['user_generated_intelligence'].append({
            'id': ugi.id, 'content_hash': ugi.content_hash,
            'modality': ugi.modality, 'exam_type': ugi.exam_type,
            'body_section': ugi.body_section,
            'clinical_question': ugi.clinical_question,
            'raw_teaching_point': ugi.raw_teaching_point,
            'raw_differentials': ugi.raw_differentials,
            'diagnosis': ugi.diagnosis, 'notes': ugi.notes,
            'pitfalls': ugi.pitfalls,
            'enriched_differentials': ugi.enriched_differentials,
            'search_tags': ugi.search_tags,
            'processing_model': ugi.processing_model,
            'processing_tokens': ugi.processing_tokens,
            'processed_at': ugi.processed_at.isoformat() if ugi.processed_at else None,
            'processing_status': ugi.processing_status,
            'is_verified': ugi.is_verified,
            'verified_by_user_id': ugi.verified_by_user_id,
            'verified_at': ugi.verified_at.isoformat() if ugi.verified_at else None,
            'created_by_user_id': ugi.created_by_user_id,
            'created_at': ugi.created_at.isoformat() if ugi.created_at else None,
            'updated_at': ugi.updated_at.isoformat() if ugi.updated_at else None,
        })

    # ==================== SNIPPET MEDIA ====================

    for sr in SnippetReference.query.all():
        backup_data['snippet_references'].append({
            'id': sr.id, 'algorithm_id': sr.algorithm_id,
            'ref_number': sr.ref_number, 'title': sr.title,
            'url': sr.url, 'journal': sr.journal, 'year': sr.year,
            'created_at': sr.created_at.isoformat() if sr.created_at else None,
        })

    for sd in SnippetDocument.query.all():
        backup_data['snippet_documents'].append({
            'id': sd.id, 'algorithm_id': sd.algorithm_id,
            'title': sd.title,
            'cloudinary_url': sd.cloudinary_url,
            'cloudinary_public_id': sd.cloudinary_public_id,
            'file_type': sd.file_type, 'file_size_kb': sd.file_size_kb,
            'uploaded_by_user_id': sd.uploaded_by_user_id,
            'created_at': sd.created_at.isoformat() if sd.created_at else None,
        })

    for si in SnippetImage.query.all():
        backup_data['snippet_images'].append({
            'id': si.id, 'algorithm_id': si.algorithm_id,
            'source_url': si.source_url, 'source_domain': si.source_domain,
            'thumbnail_url': si.thumbnail_url,
            'image_type': si.image_type, 'modality': si.modality,
            'description': si.description, 'display_order': si.display_order,
            'license': si.license, 'attribution': si.attribution,
            'added_by_user_id': si.added_by_user_id,
            'created_at': si.created_at.isoformat() if si.created_at else None,
        })

    # ==================== MDT MODULE ====================

    for mm in MdtMeeting.query.all():
        backup_data['mdt_meetings'].append({
            'id': mm.id, 'user_id': mm.user_id,
            'name': mm.name, 'mdt_type': mm.mdt_type,
            'date': mm.date.isoformat() if mm.date else None,
            'is_recurring': mm.is_recurring,
            'created_at': mm.created_at.isoformat() if mm.created_at else None,
            'updated_at': mm.updated_at.isoformat() if mm.updated_at else None,
        })

    for mc in MdtCase.query.all():
        backup_data['mdt_cases'].append({
            'id': mc.id, 'user_id': mc.user_id,
            'meeting_id': mc.meeting_id,
            'case_reference': mc.case_reference,
            'diagnosis': mc.diagnosis, 'status': mc.status,
            'clinical_history': mc.clinical_history,
            'imaging_findings': mc.imaging_findings,
            'histology_biopsy': mc.histology_biopsy,
            'lab_values': mc.lab_values,
            'additional_notes': mc.additional_notes,
            'pre_mdt_summary': mc.pre_mdt_summary,
            'mdt_consensus': mc.mdt_consensus,
            'action_plan': mc.action_plan,
            'follow_up_date': mc.follow_up_date.isoformat() if mc.follow_up_date else None,
            'linked_case_id': mc.linked_case_id,
            'source_smart_reporter_session_id': mc.source_smart_reporter_session_id,
            'created_at': mc.created_at.isoformat() if mc.created_at else None,
            'updated_at': mc.updated_at.isoformat() if mc.updated_at else None,
        })

    # ==================== OSCE GUIDE ====================

    for oc in OsceCase.query.all():
        backup_data['osce_cases'].append({
            'id': oc.id, 'code': oc.code, 'diagnosis': oc.diagnosis,
            'modality': oc.modality, 'category': oc.category,
            'difficulty': oc.difficulty, 'osce_data': oc.osce_data,
            'content_html': oc.content_html,
            'linked_case_id': oc.linked_case_id,
            'linked_case_ids': oc.linked_case_ids,
            'reference_links': oc.reference_links,
            'is_published': oc.is_published, 'sort_order': oc.sort_order,
            'created_at': oc.created_at.isoformat() if oc.created_at else None,
            'updated_at': oc.updated_at.isoformat() if oc.updated_at else None,
        })

    for oi in OsceCaseImage.query.all():
        backup_data['osce_case_images'].append({
            'id': oi.id, 'osce_case_id': oi.osce_case_id,
            'image_url': oi.image_url, 'image_public_id': oi.image_public_id,
            'image_thumbnail_url': oi.image_thumbnail_url,
            'image_description': oi.image_description,
            'attribution': oi.attribution, 'source_url': oi.source_url,
            'is_annotated': oi.is_annotated or False,
            'paired_image_id': oi.paired_image_id,
            'sort_order': oi.sort_order,
            'created_at': oi.created_at.isoformat() if oi.created_at else None,
        })

    # ==================== AUDIT & COMPLIANCE ====================

    for pol in PiiOverrideLog.query.all():
        backup_data['pii_override_logs'].append({
            'id': pol.id, 'user_id': pol.user_id,
            'action': pol.action, 'flagged_types': pol.flagged_types,
            'flagged_count': pol.flagged_count,
            'target_url': pol.target_url,
            'created_at': pol.created_at.isoformat() if pol.created_at else None,
        })

    for rle in RateLimitEntry.query.all():
        backup_data['rate_limit_entries'].append({
            'id': rle.id, 'key': rle.key,
            'endpoint': rle.endpoint,
            'hit_at': rle.hit_at.isoformat() if rle.hit_at else None,
        })

    for el in ErasureLog.query.all():
        backup_data['erasure_logs'].append({
            'id': el.id, 'erasure_type': el.erasure_type,
            'initiated_by_user_id': el.initiated_by_user_id,
            'target_user_email_hash': el.target_user_email_hash,
            'records_deleted': el.records_deleted,
            'created_at': el.created_at.isoformat() if el.created_at else None,
        })

    for aal in AdminActionLog.query.all():
        backup_data['admin_action_logs'].append({
            'id': aal.id, 'user_id': aal.user_id,
            'action': aal.action,
            'target_type': aal.target_type, 'target_id': aal.target_id,
            'details': aal.details, 'ip_address': aal.ip_address,
            'created_at': aal.created_at.isoformat() if aal.created_at else None,
        })

    # ==================== ADDITIONAL ASSOCIATION TABLES ====================

    for row in db.session.execute(case_learning_links.select()).fetchall():
        backup_data['case_learning_links'].append({
            'id': row.id, 'case_id': row.case_id,
            'learning_question_id': row.learning_question_id,
            'created_by_user_id': row.created_by_user_id,
            'created_at': row.created_at.isoformat() if row.created_at else None,
        })

    for row in db.session.execute(content_links.select()).fetchall():
        backup_data['content_links'].append({
            'id': row.id,
            'source_type': row.source_type, 'source_id': row.source_id,
            'target_type': row.target_type, 'target_id': row.target_id,
            'created_by_user_id': row.created_by_user_id,
            'created_at': row.created_at.isoformat() if row.created_at else None,
        })

    return backup_data


@backup_bp.route('/download', methods=['GET'])
@login_required
def download_backup():
    """Download complete database backup as JSON"""
    if not check_admin():
        return jsonify({'error': 'Admin access required'}), 403

    try:
        backup_data = _build_backup_data()

        # Create JSON data
        json_data = json.dumps(backup_data, indent=2)

        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Update session with last backup time
        session['last_backup_time'] = datetime.utcnow().isoformat()

        # Encrypted backup: AES-256 via Fernet, wrapped in ZIP
        if request.args.get('encrypted') == 'true':
            try:
                from cryptography.fernet import Fernet
                import hashlib, base64, zipfile

                # Derive encryption key from app SECRET_KEY (consistent per deployment)
                secret = os.getenv('SECRET_KEY', 'fallback').encode()
                key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
                f = Fernet(key)

                encrypted_data = f.encrypt(json_data.encode('utf-8'))

                # Package in ZIP with metadata
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                    zf.writestr('backup.enc', encrypted_data)
                    zf.writestr('README.txt',
                        'RadInsights Encrypted Backup\n'
                        f'Date: {timestamp}\n'
                        'This backup is encrypted with AES-256 (Fernet).\n'
                        'Decrypt using your deployment SECRET_KEY.\n'
                    )
                zip_buffer.seek(0)
                filename = f'radinsights_backup_{timestamp}.enc.zip'

                return send_file(
                    zip_buffer,
                    mimetype='application/zip',
                    as_attachment=True,
                    download_name=filename
                )
            except Exception as enc_err:
                logger.error(f"Backup encryption failed: {enc_err}")
                return jsonify({'error': f'Encryption failed: {str(enc_err)}'}), 500

        # Plain JSON backup (default)
        json_bytes = io.BytesIO(json_data.encode('utf-8'))
        filename = f'radinsights_backup_{timestamp}.json'

        return send_file(
            json_bytes,
            mimetype='application/json',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({'error': f'Backup failed: {str(e)}'}), 500


@backup_bp.route('/scheduled-backup', methods=['GET', 'POST'])
def scheduled_backup():
    """Cron endpoint: build backup JSON and upload to Cloudflare R2.
    Keeps the last 30 daily backups; deletes older ones."""
    from flask import current_app
    import gzip

    # Auth: same pattern as other cron endpoints
    cron_secret = os.getenv('CRON_SECRET')
    if current_app.debug:
        pass  # Allow in debug mode
    elif not cron_secret:
        logger.error('CRON_SECRET not configured — rejecting scheduled backup')
        return jsonify({'error': 'CRON_SECRET not configured'}), 401
    else:
        auth = request.headers.get('Authorization', '')
        if not auth.endswith(cron_secret):
            return jsonify({'error': 'Unauthorized'}), 401

    try:
        from case_dicom_viewer import r2_service

        if not r2_service.is_configured():
            return jsonify({'error': 'R2 storage not configured'}), 503

        # Build backup data
        backup_data = _build_backup_data()
        json_bytes = json.dumps(backup_data, separators=(',', ':')).encode('utf-8')

        # Gzip compress to save storage
        compressed = gzip.compress(json_bytes)

        # Upload to R2
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        key = f'backups/radinsights_{timestamp}.json.gz'
        success = r2_service.upload_object(key, compressed, content_type='application/gzip')
        if not success:
            return jsonify({'error': 'R2 upload failed'}), 500

        size_kb = len(compressed) / 1024

        # Prune old backups — keep last 30
        pruned = 0
        listing = r2_service.list_objects(prefix='backups/', delimiter='', max_keys=1000)
        objects = sorted(listing.get('objects', []), key=lambda o: o.get('key', ''))
        if len(objects) > 30:
            old_keys = [o['key'] for o in objects[:len(objects) - 30]]
            deleted, _ = r2_service.delete_objects(old_keys)
            pruned = len(deleted)

        logger.info(f'Scheduled backup uploaded: {key} ({size_kb:.1f} KB), pruned {pruned} old backups')
        return jsonify({
            'success': True,
            'key': key,
            'size_kb': round(size_kb, 1),
            'pruned': pruned,
        }), 200

    except Exception as e:
        logger.exception('Scheduled backup failed: %s', e)
        return jsonify({'error': str(e)}), 500


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

    if not file.filename.endswith('.json') and not file.filename.endswith('.json.gz'):
        return jsonify({'error': 'Only JSON backup files are supported'}), 400

    # Handle both compressed and uncompressed uploads
    # Client compresses large files (>4MB) with gzip to fit under Vercel's 4.5MB body limit
    is_compressed = (
        request.form.get('compressed') == 'true'
        or file.filename.endswith('.gz')
    )

    try:
        # Get file size (seek to end, get position, then reset)
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning

        print(f"[IMPORT] Backup file size: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB) {'(gzip compressed)' if is_compressed else ''}")

        # Read file content in chunks
        file_content_parts = []
        chunk_size = 1024 * 1024  # 1MB chunks
        total_read = 0

        while True:
            chunk = file.read(chunk_size)
            if not chunk:
                break
            file_content_parts.append(chunk)
            total_read += len(chunk)

        raw_bytes = b''.join(file_content_parts)
        file = None
        file_content_parts = None

        # Decompress if gzip-compressed
        if is_compressed:
            import gzip
            try:
                decompressed = gzip.decompress(raw_bytes)
                print(f"[IMPORT] Decompressed {len(raw_bytes)} → {len(decompressed)} bytes ({len(decompressed) / 1024 / 1024:.2f} MB)")
                file_content = decompressed.decode('utf-8')
                raw_bytes = None
                decompressed = None
            except Exception as gz_err:
                print(f"[IMPORT] Gzip decompression failed: {gz_err}")
                return jsonify({'error': f'Failed to decompress backup file: {gz_err}'}), 400
        else:
            file_content = raw_bytes.decode('utf-8')
            raw_bytes = None

        print(f"[IMPORT] Successfully read {len(file_content)} characters from backup file")
        
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

        # Sanitize all records: convert dict/list values to JSON strings (SQLite compat)
        _sanitize_backup_data(backup_data)

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
                
                # Filter out unknown fields + sensitive credentials that should never be imported from backup
                _EXCLUDED_IMPORT_FIELDS = {'recovery_token', 'recovery_token_expires', 'notion_access_token',
                                           'anki_api_key', 'sciencedirect_session_cookies', 'locked_until',
                                           'failed_login_count', 'failed_login_last'}
                filtered_data = {k: v for k, v in user_data.items()
                                 if k not in _EXCLUDED_IMPORT_FIELDS and
                                 (k in valid_user_fields or k in ['email', 'password_hash', 'full_name', 'role', 'is_active', 'subscription_status', 'payment_status'])}
                
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

        # Import Radiology Templates (new format)
        stats['radiology_templates'] = {'added': 0, 'skipped': 0}
        for rt_data in backup_data.get('radiology_templates', []):
            if not isinstance(rt_data, dict):
                continue
            slug = rt_data.get('slug', '')
            if not slug:
                stats['radiology_templates']['skipped'] += 1
                continue
            if RadiologyTemplate.query.filter_by(slug=slug).first():
                stats['radiology_templates']['skipped'] += 1
                continue
            old_created_by = rt_data.get('created_by_user_id')
            old_verified_by = rt_data.get('verified_by_user_id')
            rt = RadiologyTemplate(
                slug=slug, title=rt_data.get('title', ''),
                origin=rt_data.get('origin', 'admin'),
                category=rt_data.get('category'),
                body_section=rt_data.get('body_section'),
                description=rt_data.get('description'), keywords=rt_data.get('keywords'),
                template_text=rt_data.get('template_text', rt_data.get('pacs_report_text')),
                source_citation=rt_data.get('source_citation'),
                guideline_version=rt_data.get('guideline_version'),
                is_available=rt_data.get('is_available', False),
                is_ai_generated=rt_data.get('is_ai_generated', False),
                verified_by_user_id=user_id_map.get(old_verified_by) if old_verified_by else None,
                verified_at=_parse_datetime_for_sqlite(rt_data.get('verified_at')),
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
            stats['radiology_templates']['added'] += 1

        # Import Reporting Algorithms (new format)
        stats['reporting_algorithms'] = {'added': 0, 'skipped': 0}
        for ra_data in backup_data.get('reporting_algorithms', []):
            if not isinstance(ra_data, dict):
                continue
            slug = ra_data.get('slug', '')
            if not slug:
                stats['reporting_algorithms']['skipped'] += 1
                continue
            if ReportingAlgorithm.query.filter_by(slug=slug).first():
                stats['reporting_algorithms']['skipped'] += 1
                continue
            old_created_by = ra_data.get('created_by_user_id')
            old_verified_by = ra_data.get('verified_by_user_id')
            ra = ReportingAlgorithm(
                slug=slug, title=ra_data.get('title', ''),
                origin=ra_data.get('origin', 'admin'),
                category=ra_data.get('category', ''),
                body_section=ra_data.get('body_section'),
                description=ra_data.get('description'), keywords=ra_data.get('keywords'),
                template_html=ra_data.get('template_html'),
                algorithm_html=ra_data.get('algorithm_html'),
                source_citation=ra_data.get('source_citation'),
                guideline_version=ra_data.get('guideline_version'),
                is_available=ra_data.get('is_available', False),
                is_ai_generated=ra_data.get('is_ai_generated', False),
                verified_by_user_id=user_id_map.get(old_verified_by) if old_verified_by else None,
                verified_at=_parse_datetime_for_sqlite(ra_data.get('verified_at')),
                generation_prompt=ra_data.get('generation_prompt'),
                generation_model=ra_data.get('generation_model'),
                generated_at=_parse_datetime_for_sqlite(ra_data.get('generated_at')),
                created_by_user_id=user_id_map.get(old_created_by) if old_created_by else None,
                last_edit_note=ra_data.get('last_edit_note'),
            )
            if ra_data.get('created_at'):
                ra.created_at = _parse_datetime_for_sqlite(ra_data['created_at']) or datetime.utcnow()
            if ra_data.get('updated_at'):
                ra.updated_at = _parse_datetime_for_sqlite(ra_data['updated_at']) or datetime.utcnow()
            db.session.add(ra)
            stats['reporting_algorithms']['added'] += 1

        # Import legacy reporting_templates (backward compat — route by category)
        RADIOLOGY_CATS = {'radiology_template', 'personal_template'}
        for rt_data in backup_data.get('reporting_templates', []):
            if not isinstance(rt_data, dict):
                continue
            slug = rt_data.get('slug', '')
            if not slug:
                continue
            cat = rt_data.get('category', '')
            old_created_by = rt_data.get('created_by_user_id')
            old_verified_by = rt_data.get('verified_by_user_id')
            if cat in RADIOLOGY_CATS:
                if RadiologyTemplate.query.filter_by(slug=slug).first():
                    continue
                origin = 'personal' if cat == 'personal_template' else 'admin'
                rt = RadiologyTemplate(
                    slug=slug, title=rt_data.get('title', ''), origin=origin,
                    body_section=rt_data.get('body_section'),
                    description=rt_data.get('description'), keywords=rt_data.get('keywords'),
                    template_text=rt_data.get('pacs_report_text'),
                    source_citation=rt_data.get('source_citation'),
                    guideline_version=rt_data.get('guideline_version'),
                    is_available=rt_data.get('is_available', False),
                    is_ai_generated=rt_data.get('is_ai_generated', False),
                    verified_by_user_id=user_id_map.get(old_verified_by) if old_verified_by else None,
                    verified_at=_parse_datetime_for_sqlite(rt_data.get('verified_at')),
                    generation_prompt=rt_data.get('generation_prompt'),
                    generation_model=rt_data.get('generation_model'),
                    generated_at=_parse_datetime_for_sqlite(rt_data.get('generated_at')),
                    created_by_user_id=user_id_map.get(old_created_by) if old_created_by else None,
                    last_edit_note=rt_data.get('last_edit_note'),
                )
                if rt_data.get('created_at'):
                    rt.created_at = _parse_datetime_for_sqlite(rt_data['created_at']) or datetime.utcnow()
                db.session.add(rt)
                stats['radiology_templates']['added'] += 1
            else:
                if ReportingAlgorithm.query.filter_by(slug=slug).first():
                    continue
                if cat in ('smart_reporter_cache', 'ai_generated'):
                    origin = 'user'
                elif cat == 'anatomy':
                    origin = 'anatomy_cache'
                else:
                    origin = 'admin'
                ra = ReportingAlgorithm(
                    slug=slug, title=rt_data.get('title', ''), origin=origin,
                    category=cat, body_section=rt_data.get('body_section'),
                    description=rt_data.get('description'), keywords=rt_data.get('keywords'),
                    template_html=rt_data.get('template_html'),
                    algorithm_html=rt_data.get('algorithm_html'),
                    source_citation=rt_data.get('source_citation'),
                    guideline_version=rt_data.get('guideline_version'),
                    is_available=rt_data.get('is_available', False),
                    is_ai_generated=rt_data.get('is_ai_generated', False),
                    verified_by_user_id=user_id_map.get(old_verified_by) if old_verified_by else None,
                    verified_at=_parse_datetime_for_sqlite(rt_data.get('verified_at')),
                    generation_prompt=rt_data.get('generation_prompt'),
                    generation_model=rt_data.get('generation_model'),
                    generated_at=_parse_datetime_for_sqlite(rt_data.get('generated_at')),
                    created_by_user_id=user_id_map.get(old_created_by) if old_created_by else None,
                    last_edit_note=rt_data.get('last_edit_note'),
                )
                if rt_data.get('created_at'):
                    ra.created_at = _parse_datetime_for_sqlite(rt_data['created_at']) or datetime.utcnow()
                db.session.add(ra)
                stats['reporting_algorithms']['added'] += 1

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

        # Import Content Requests
        stats['content_requests'] = {'added': 0, 'skipped': 0}
        for cr_data in backup_data.get('content_requests', []):
            if not isinstance(cr_data, dict):
                continue
            title = cr_data.get('title', '')
            old_user_id = cr_data.get('user_id')
            if not title or not old_user_id:
                stats['content_requests']['skipped'] += 1
                continue
            mapped_user_id = user_id_map.get(old_user_id)
            if not mapped_user_id:
                stats['content_requests']['skipped'] += 1
                continue
            # Skip if same user already has a request with same title
            existing = ContentRequest.query.filter_by(user_id=mapped_user_id, title=title).first()
            if existing:
                stats['content_requests']['skipped'] += 1
                continue
            cr = ContentRequest(
                user_id=mapped_user_id,
                request_type=cr_data.get('request_type', 'template'),
                title=title,
                description=cr_data.get('description'),
                body_section=cr_data.get('body_section'),
                status=cr_data.get('status', 'pending'),
                admin_notes=cr_data.get('admin_notes'),
            )
            if cr_data.get('created_at'):
                cr.created_at = _parse_datetime_for_sqlite(cr_data['created_at']) or datetime.utcnow()
            db.session.add(cr)
            stats['content_requests']['added'] += 1

        # Import Radiology Pearls
        stats['radiology_pearls'] = {'added': 0, 'skipped': 0}
        for pearl_data in backup_data.get('radiology_pearls', []):
            if not isinstance(pearl_data, dict):
                continue
            content_hash = pearl_data.get('content_hash', '')
            pearl_text = pearl_data.get('pearl_text', '')
            if not content_hash or not pearl_text:
                stats['radiology_pearls']['skipped'] += 1
                continue
            existing = RadiologyPearl.query.filter_by(content_hash=content_hash).first()
            if existing:
                stats['radiology_pearls']['skipped'] += 1
                continue
            pearl = RadiologyPearl(
                content_hash=content_hash,
                pearl_text=pearl_text,
                body_section=pearl_data.get('body_section'),
                modality=pearl_data.get('modality'),
                tags=pearl_data.get('tags'),
                source_report_context=pearl_data.get('source_report_context'),
                is_verified=pearl_data.get('is_verified', False),
                created_by_user_id=user_id_map.get(pearl_data.get('created_by_user_id')),
                verified_by_user_id=user_id_map.get(pearl_data.get('verified_by_user_id')),
            )
            if pearl_data.get('verified_at'):
                pearl.verified_at = _parse_datetime_for_sqlite(pearl_data['verified_at'])
            if pearl_data.get('created_at'):
                pearl.created_at = _parse_datetime_for_sqlite(pearl_data['created_at']) or datetime.utcnow()
            db.session.add(pearl)
            stats['radiology_pearls']['added'] += 1

        # Import Imported Case Staging
        stats['imported_case_staging'] = {'added': 0, 'skipped': 0}
        for ics_data in backup_data.get('imported_case_staging', []):
            if not isinstance(ics_data, dict):
                continue
            batch_id = ics_data.get('import_batch_id', '')
            original_id = ics_data.get('original_id')
            if not batch_id:
                stats['imported_case_staging']['skipped'] += 1
                continue
            # Skip if same batch+original_id exists
            existing = ImportedCaseStaging.query.filter_by(
                import_batch_id=batch_id, original_id=original_id
            ).first() if original_id else None
            if existing:
                stats['imported_case_staging']['skipped'] += 1
                continue
            old_enriched_by = ics_data.get('enriched_by_user_id')
            old_approved_by = ics_data.get('approved_by_user_id')
            ics = ImportedCaseStaging(
                original_id=original_id,
                case_number=ics_data.get('case_number'),
                diagnosis=ics_data.get('diagnosis', ''),
                questions=ics_data.get('questions', ''),
                answers=ics_data.get('answers', ''),
                discussion=ics_data.get('discussion'),
                is_public=ics_data.get('is_public', False),
                enrichment_status=ics_data.get('enrichment_status', 'pending'),
                enriched_by_user_id=user_id_map.get(old_enriched_by) if old_enriched_by else None,
                enriched_at=_parse_datetime_for_sqlite(ics_data.get('enriched_at')),
                enrichment_notes=ics_data.get('enrichment_notes'),
                approved_by_user_id=user_id_map.get(old_approved_by) if old_approved_by else None,
                approved_at=_parse_datetime_for_sqlite(ics_data.get('approved_at')),
                approval_notes=ics_data.get('approval_notes'),
                is_replacement=ics_data.get('is_replacement', False),
                import_batch_id=batch_id,
                source_system=ics_data.get('source_system', 'frcr_examiner'),
                import_timestamp=_parse_datetime_for_sqlite(ics_data.get('import_timestamp')),
            )
            # Enum fields need special handling
            module_val = ics_data.get('module')
            if module_val:
                try:
                    ics.module = FRCRModule(module_val)
                except (ValueError, KeyError):
                    pass
            body_part_val = ics_data.get('body_part')
            if body_part_val:
                try:
                    ics.body_part = BodyPart(body_part_val)
                except (ValueError, KeyError):
                    pass
            age_group_val = ics_data.get('age_group')
            if age_group_val:
                try:
                    ics.age_group = AgeGroup(age_group_val)
                except (ValueError, KeyError):
                    pass
            if ics_data.get('created_at'):
                ics.created_at = _parse_datetime_for_sqlite(ics_data['created_at']) or datetime.utcnow()
            if ics_data.get('updated_at'):
                ics.updated_at = _parse_datetime_for_sqlite(ics_data['updated_at']) or datetime.utcnow()
            db.session.add(ics)
            stats['imported_case_staging']['added'] += 1

        # ==================== VETTING SESSIONS ====================
        stats['vetting_sessions'] = {'added': 0, 'skipped': 0}
        for vs_data in backup_data.get('vetting_sessions', []):
            if not isinstance(vs_data, dict):
                continue
            vs = VettingSession(
                user_id=user_id_map.get(vs_data.get('user_id')),
                raw_clinical_text=vs_data.get('raw_clinical_text'),
                modality_hint=vs_data.get('modality_hint'),
                cleaned_clinical_text=vs_data.get('cleaned_clinical_text'),
                study_type=vs_data.get('study_type'),
                safety_checks_json=vs_data.get('safety_checks_json'),
                protocol_source=vs_data.get('protocol_source'),
                protocol_id=vs_data.get('protocol_id'),
                final_clinical_details=vs_data.get('final_clinical_details'),
                final_shorthand=vs_data.get('final_shorthand'),
                final_detailed_html=vs_data.get('final_detailed_html'),
                final_special_notes=vs_data.get('final_special_notes'),
                ai_model=vs_data.get('ai_model'),
                ai_tokens_used=vs_data.get('ai_tokens_used'),
            )
            if vs_data.get('created_at'):
                vs.created_at = _parse_datetime_for_sqlite(vs_data['created_at']) or datetime.utcnow()
            db.session.add(vs)
            stats['vetting_sessions']['added'] += 1

        # ==================== VETTING ALGORITHMS ====================
        stats['vetting_algorithms'] = {'added': 0, 'skipped': 0}
        for va_data in backup_data.get('vetting_algorithms', []):
            if not isinstance(va_data, dict):
                continue
            slug = va_data.get('slug', '')
            if not slug:
                stats['vetting_algorithms']['skipped'] += 1
                continue
            existing = VettingAlgorithm.query.filter_by(slug=slug).first()
            if existing:
                stats['vetting_algorithms']['skipped'] += 1
                continue
            va = VettingAlgorithm(
                algorithm_key=va_data.get('algorithm_key'),
                title=va_data.get('title', ''), slug=slug,
                body_section=va_data.get('body_section'),
                clinical_scenario=va_data.get('clinical_scenario'),
                entry_criteria_json=va_data.get('entry_criteria_json'),
                steps_json=va_data.get('steps_json'),
                safety_json=va_data.get('safety_json'),
                tags=va_data.get('tags'), keywords=va_data.get('keywords'),
                origin=va_data.get('origin', 'admin'),
                is_published=va_data.get('is_published', True),
                is_verified=va_data.get('is_verified', False),
                verified_by_user_id=user_id_map.get(va_data.get('verified_by_user_id')),
            )
            if va_data.get('verified_at'):
                va.verified_at = _parse_datetime_for_sqlite(va_data['verified_at'])
            if va_data.get('created_at'):
                va.created_at = _parse_datetime_for_sqlite(va_data['created_at']) or datetime.utcnow()
            if va_data.get('updated_at'):
                va.updated_at = _parse_datetime_for_sqlite(va_data['updated_at'])
            db.session.add(va)
            stats['vetting_algorithms']['added'] += 1

        # ==================== ADMIN DOCUMENTS ====================
        stats['admin_documents'] = {'added': 0, 'skipped': 0}
        for doc_data in backup_data.get('admin_documents', []):
            if not isinstance(doc_data, dict):
                continue
            slug = doc_data.get('slug', '')
            if not slug:
                stats['admin_documents']['skipped'] += 1
                continue
            existing = AdminDocument.query.filter_by(slug=slug).first()
            if existing:
                stats['admin_documents']['skipped'] += 1
                continue
            doc = AdminDocument(
                slug=slug, title=doc_data.get('title', ''),
                category=doc_data.get('category', 'general'),
                content_html=doc_data.get('content_html'),
                last_edited_by=user_id_map.get(doc_data.get('last_edited_by')),
            )
            if doc_data.get('created_at'):
                doc.created_at = _parse_datetime_for_sqlite(doc_data['created_at']) or datetime.utcnow()
            if doc_data.get('updated_at'):
                doc.updated_at = _parse_datetime_for_sqlite(doc_data['updated_at'])
            db.session.add(doc)
            stats['admin_documents']['added'] += 1

        # ==================== CLAUDE MEMORY UPDATES ====================
        stats['claude_memory_updates'] = {'added': 0, 'skipped': 0}
        for cmu_data in backup_data.get('claude_memory_updates', []):
            if not isinstance(cmu_data, dict):
                continue
            cmu = ClaudeMemoryUpdate(
                category=cmu_data.get('category'),
                summary=cmu_data.get('summary', ''),
                details=cmu_data.get('details'),
                source_doc_slug=cmu_data.get('source_doc_slug'),
                created_by=user_id_map.get(cmu_data.get('created_by')),
                is_synced=cmu_data.get('is_synced', False),
            )
            if cmu_data.get('created_at'):
                cmu.created_at = _parse_datetime_for_sqlite(cmu_data['created_at']) or datetime.utcnow()
            if cmu_data.get('synced_at'):
                cmu.synced_at = _parse_datetime_for_sqlite(cmu_data['synced_at'])
            db.session.add(cmu)
            stats['claude_memory_updates']['added'] += 1

        # ==================== TOUR CAPTURES ====================
        stats['tour_captures'] = {'added': 0, 'skipped': 0}
        for tc_data in backup_data.get('tour_captures', []):
            if not isinstance(tc_data, dict):
                continue
            tc = TourCapture(
                tour_name=tc_data.get('tour_name', ''),
                step_number=tc_data.get('step_number', 0),
                step_label=tc_data.get('step_label'),
                user_input=tc_data.get('user_input'),
                response_json=tc_data.get('response_json'),
                notes=tc_data.get('notes'),
                screenshot_url=tc_data.get('screenshot_url'),
            )
            if tc_data.get('created_at'):
                tc.created_at = _parse_datetime_for_sqlite(tc_data['created_at']) or datetime.utcnow()
            db.session.add(tc)
            stats['tour_captures']['added'] += 1

        # ==================== PEER REVIEW CLAIMS ====================
        stats['peer_review_claims'] = {'added': 0, 'skipped': 0}
        for prc_data in backup_data.get('peer_review_claims', []):
            if not isinstance(prc_data, dict):
                continue
            prc = PeerReviewClaim(
                content_type=prc_data.get('content_type'),
                content_id=prc_data.get('content_id'),
                claim_text=prc_data.get('claim_text'),
                claim_type=prc_data.get('claim_type'),
                gemini_verdict=prc_data.get('gemini_verdict'),
                gemini_confidence=prc_data.get('gemini_confidence'),
                gemini_reasoning=prc_data.get('gemini_reasoning'),
                gemini_correction=prc_data.get('gemini_correction'),
                gemini_model=prc_data.get('gemini_model'),
                admin_override=prc_data.get('admin_override'),
                admin_notes=prc_data.get('admin_notes'),
                admin_reference_url=prc_data.get('admin_reference_url'),
                admin_reference_title=prc_data.get('admin_reference_title'),
                reviewed_by_admin_id=user_id_map.get(prc_data.get('reviewed_by_admin_id')),
                context_body_section=prc_data.get('context_body_section'),
                context_modality=prc_data.get('context_modality'),
                context_topic=prc_data.get('context_topic'),
            )
            if prc_data.get('reviewed_at'):
                prc.reviewed_at = _parse_datetime_for_sqlite(prc_data['reviewed_at'])
            if prc_data.get('created_at'):
                prc.created_at = _parse_datetime_for_sqlite(prc_data['created_at']) or datetime.utcnow()
            db.session.add(prc)
            stats['peer_review_claims']['added'] += 1

        # ==================== PEER REVIEW FLAGS ====================
        stats['peer_review_flags'] = {'added': 0, 'skipped': 0}
        for prf_data in backup_data.get('peer_review_flags', []):
            if not isinstance(prf_data, dict):
                continue
            prf = PeerReviewFlag(
                user_id=user_id_map.get(prf_data.get('user_id')),
                content_type=prf_data.get('content_type'),
                content_id=prf_data.get('content_id'),
                section=prf_data.get('section'),
                details=prf_data.get('details'),
                claim_text=prf_data.get('claim_text'),
                selected_text=prf_data.get('selected_text'),
                error_type=prf_data.get('error_type'),
                severity=prf_data.get('severity'),
                page_url=prf_data.get('page_url'),
                is_resolved=prf_data.get('is_resolved', False),
                resolved_by_user_id=user_id_map.get(prf_data.get('resolved_by_user_id')),
                resolution_notes=prf_data.get('resolution_notes'),
            )
            if prf_data.get('resolved_at'):
                prf.resolved_at = _parse_datetime_for_sqlite(prf_data['resolved_at'])
            if prf_data.get('created_at'):
                prf.created_at = _parse_datetime_for_sqlite(prf_data['created_at']) or datetime.utcnow()
            db.session.add(prf)
            stats['peer_review_flags']['added'] += 1

        # ==================== MANUAL VERIFICATIONS ====================
        stats['manual_verifications'] = {'added': 0, 'skipped': 0}
        for mv_data in backup_data.get('manual_verifications', []):
            if not isinstance(mv_data, dict):
                continue
            mv = ManualVerification(
                content_type=mv_data.get('content_type'),
                content_id=mv_data.get('content_id'),
                selected_text=mv_data.get('selected_text'),
                custom_label=mv_data.get('custom_label'),
                pubmed_doi=mv_data.get('pubmed_doi'),
                pubmed_pmid=mv_data.get('pubmed_pmid'),
                pubmed_title=mv_data.get('pubmed_title'),
                pubmed_authors=mv_data.get('pubmed_authors'),
                pubmed_journal=mv_data.get('pubmed_journal'),
                pubmed_year=mv_data.get('pubmed_year'),
                verified_by_user_id=user_id_map.get(mv_data.get('verified_by_user_id')),
            )
            if mv_data.get('created_at'):
                mv.created_at = _parse_datetime_for_sqlite(mv_data['created_at']) or datetime.utcnow()
            db.session.add(mv)
            stats['manual_verifications']['added'] += 1

        # ==================== RADIQ QUERIES ====================
        stats['radiq_queries'] = {'added': 0, 'skipped': 0}
        for rq_data in backup_data.get('radiq_queries', []):
            if not isinstance(rq_data, dict):
                continue
            rq = RadIQQuery(
                user_id=user_id_map.get(rq_data.get('user_id')),
                category=rq_data.get('category'),
                question=rq_data.get('question'),
                response_text=rq_data.get('response_text'),
            )
            if rq_data.get('created_at'):
                rq.created_at = _parse_datetime_for_sqlite(rq_data['created_at']) or datetime.utcnow()
            db.session.add(rq)
            stats['radiq_queries']['added'] += 1

        # ==================== RADIQ FEEDBACK ====================
        stats['radiq_feedback'] = {'added': 0, 'skipped': 0}
        for rf_data in backup_data.get('radiq_feedback', []):
            if not isinstance(rf_data, dict):
                continue
            rf = RadIQFeedback(
                query_id=rf_data.get('query_id'),
                user_id=user_id_map.get(rf_data.get('user_id')),
                reason=rf_data.get('reason'),
                details=rf_data.get('details'),
                is_resolved=rf_data.get('is_resolved', False),
                resolved_by_user_id=user_id_map.get(rf_data.get('resolved_by_user_id')),
                resolution_notes=rf_data.get('resolution_notes'),
            )
            if rf_data.get('resolved_at'):
                rf.resolved_at = _parse_datetime_for_sqlite(rf_data['resolved_at'])
            if rf_data.get('created_at'):
                rf.created_at = _parse_datetime_for_sqlite(rf_data['created_at']) or datetime.utcnow()
            db.session.add(rf)
            stats['radiq_feedback']['added'] += 1

        # ==================== REPORTING SESSIONS ====================
        stats['reporting_sessions'] = {'added': 0, 'skipped': 0}
        for rs_data in backup_data.get('reporting_sessions', []):
            if not isinstance(rs_data, dict):
                continue
            rs = ReportingSession(
                user_id=user_id_map.get(rs_data.get('user_id')),
                clinical_question=rs_data.get('clinical_question'),
                modality=rs_data.get('modality'),
                body_section=rs_data.get('body_section'),
                algorithm_tree_json=rs_data.get('algorithm_tree_json'),
                walkthrough_answers_json=rs_data.get('walkthrough_answers_json'),
                report_text=rs_data.get('report_text'),
                status=rs_data.get('status'),
                provider=rs_data.get('provider'),
                model_name=rs_data.get('model_name'),
                generation_tokens=rs_data.get('generation_tokens'),
                ask_claude_count=rs_data.get('ask_claude_count', 0),
            )
            if rs_data.get('created_at'):
                rs.created_at = _parse_datetime_for_sqlite(rs_data['created_at']) or datetime.utcnow()
            if rs_data.get('completed_at'):
                rs.completed_at = _parse_datetime_for_sqlite(rs_data['completed_at'])
            db.session.add(rs)
            stats['reporting_sessions']['added'] += 1

        # ==================== PUBLISHED REPORTS ====================
        stats['published_reports'] = {'added': 0, 'skipped': 0}
        for pr_data in backup_data.get('published_reports', []):
            if not isinstance(pr_data, dict):
                continue
            pr = PublishedReport(
                session_id=pr_data.get('session_id'),
                user_id=user_id_map.get(pr_data.get('user_id')),
                clinical_question=pr_data.get('clinical_question'),
                modality=pr_data.get('modality'),
                body_section=pr_data.get('body_section'),
                report_text=pr_data.get('report_text'),
                algorithm_tree_json=pr_data.get('algorithm_tree_json'),
                contributor_name=pr_data.get('contributor_name'),
            )
            if pr_data.get('published_at'):
                pr.published_at = _parse_datetime_for_sqlite(pr_data['published_at']) or datetime.utcnow()
            db.session.add(pr)
            stats['published_reports']['added'] += 1

        # ==================== LEARNING QUESTIONS ====================
        stats['learning_questions'] = {'added': 0, 'skipped': 0}
        for lq_data in backup_data.get('learning_questions', []):
            if not isinstance(lq_data, dict):
                continue
            content_hash = lq_data.get('content_hash', '')
            if content_hash:
                existing = LearningQuestion.query.filter_by(content_hash=content_hash).first()
                if existing:
                    stats['learning_questions']['skipped'] += 1
                    continue
            lq = LearningQuestion(
                question_type=lq_data.get('question_type'),
                body_section=lq_data.get('body_section'),
                modality=lq_data.get('modality'),
                module=lq_data.get('module'),
                title=lq_data.get('title', ''),
                html_content=lq_data.get('html_content'),
                source_report_context=lq_data.get('source_report_context'),
                tags=lq_data.get('tags'),
                search_tags=lq_data.get('search_tags'),
                description=lq_data.get('description'),
                content_hash=content_hash,
                created_by_user_id=user_id_map.get(lq_data.get('created_by_user_id')),
            )
            if lq_data.get('created_at'):
                lq.created_at = _parse_datetime_for_sqlite(lq_data['created_at']) or datetime.utcnow()
            db.session.add(lq)
            stats['learning_questions']['added'] += 1

        # ==================== LEARNING QUESTION PROGRESS ====================
        stats['learning_question_progress'] = {'added': 0, 'skipped': 0}
        for lqp_data in backup_data.get('learning_question_progress', []):
            if not isinstance(lqp_data, dict):
                continue
            lqp = LearningQuestionProgress(
                user_id=user_id_map.get(lqp_data.get('user_id')),
                learning_question_id=lqp_data.get('learning_question_id'),
                score=lqp_data.get('score'),
                best_score=lqp_data.get('best_score'),
                times_attempted=lqp_data.get('times_attempted'),
            )
            if lqp_data.get('last_attempted_at'):
                lqp.last_attempted_at = _parse_datetime_for_sqlite(lqp_data['last_attempted_at'])
            if lqp_data.get('created_at'):
                lqp.created_at = _parse_datetime_for_sqlite(lqp_data['created_at']) or datetime.utcnow()
            db.session.add(lqp)
            stats['learning_question_progress']['added'] += 1

        # ==================== LEARNING QUESTION REFERENCES ====================
        stats['learning_question_references'] = {'added': 0, 'skipped': 0}
        for lqr_data in backup_data.get('learning_question_references', []):
            if not isinstance(lqr_data, dict):
                continue
            lqr = LearningQuestionReference(
                learning_question_id=lqr_data.get('learning_question_id'),
                ref_number=lqr_data.get('ref_number'),
                title=lqr_data.get('title'),
                url=lqr_data.get('url'),
                journal=lqr_data.get('journal'),
                year=lqr_data.get('year'),
            )
            if lqr_data.get('created_at'):
                lqr.created_at = _parse_datetime_for_sqlite(lqr_data['created_at']) or datetime.utcnow()
            db.session.add(lqr)
            stats['learning_question_references']['added'] += 1

        # ==================== CONTENT INTELLIGENCE ====================
        stats['content_intelligence'] = {'added': 0, 'skipped': 0}
        for ci_data in backup_data.get('content_intelligence', []):
            if not isinstance(ci_data, dict):
                continue
            ci = ContentIntelligence(
                content_type=ci_data.get('content_type'),
                content_id=ci_data.get('content_id'),
                summary=ci_data.get('summary'),
                search_tags=ci_data.get('search_tags'),
                cross_links_json=ci_data.get('cross_links_json'),
                processing_model=ci_data.get('processing_model'),
                processing_tokens=ci_data.get('processing_tokens'),
                is_verified=ci_data.get('is_verified', False),
                verified_by_user_id=user_id_map.get(ci_data.get('verified_by_user_id')),
            )
            if ci_data.get('processed_at'):
                ci.processed_at = _parse_datetime_for_sqlite(ci_data['processed_at'])
            if ci_data.get('verified_at'):
                ci.verified_at = _parse_datetime_for_sqlite(ci_data['verified_at'])
            if ci_data.get('created_at'):
                ci.created_at = _parse_datetime_for_sqlite(ci_data['created_at']) or datetime.utcnow()
            if ci_data.get('updated_at'):
                ci.updated_at = _parse_datetime_for_sqlite(ci_data['updated_at'])
            db.session.add(ci)
            stats['content_intelligence']['added'] += 1

        # ==================== USER GENERATED INTELLIGENCE ====================
        stats['user_generated_intelligence'] = {'added': 0, 'skipped': 0}
        for ugi_data in backup_data.get('user_generated_intelligence', []):
            if not isinstance(ugi_data, dict):
                continue
            content_hash = ugi_data.get('content_hash', '')
            if content_hash:
                existing = UserGeneratedIntelligence.query.filter_by(content_hash=content_hash).first()
                if existing:
                    stats['user_generated_intelligence']['skipped'] += 1
                    continue
            ugi = UserGeneratedIntelligence(
                content_hash=content_hash,
                modality=ugi_data.get('modality'),
                exam_type=ugi_data.get('exam_type'),
                body_section=ugi_data.get('body_section'),
                clinical_question=ugi_data.get('clinical_question'),
                raw_teaching_point=ugi_data.get('raw_teaching_point'),
                raw_differentials=ugi_data.get('raw_differentials'),
                diagnosis=ugi_data.get('diagnosis'),
                notes=ugi_data.get('notes'),
                pitfalls=ugi_data.get('pitfalls'),
                enriched_differentials=ugi_data.get('enriched_differentials'),
                search_tags=ugi_data.get('search_tags'),
                processing_model=ugi_data.get('processing_model'),
                processing_tokens=ugi_data.get('processing_tokens'),
                processing_status=ugi_data.get('processing_status', 'pending'),
                is_verified=ugi_data.get('is_verified', False),
                verified_by_user_id=user_id_map.get(ugi_data.get('verified_by_user_id')),
                created_by_user_id=user_id_map.get(ugi_data.get('created_by_user_id')),
            )
            if ugi_data.get('processed_at'):
                ugi.processed_at = _parse_datetime_for_sqlite(ugi_data['processed_at'])
            if ugi_data.get('verified_at'):
                ugi.verified_at = _parse_datetime_for_sqlite(ugi_data['verified_at'])
            if ugi_data.get('created_at'):
                ugi.created_at = _parse_datetime_for_sqlite(ugi_data['created_at']) or datetime.utcnow()
            if ugi_data.get('updated_at'):
                ugi.updated_at = _parse_datetime_for_sqlite(ugi_data['updated_at'])
            db.session.add(ugi)
            stats['user_generated_intelligence']['added'] += 1

        # ==================== SNIPPET REFERENCES ====================
        stats['snippet_references'] = {'added': 0, 'skipped': 0}
        for sr_data in backup_data.get('snippet_references', []):
            if not isinstance(sr_data, dict):
                continue
            sr = SnippetReference(
                algorithm_id=sr_data.get('algorithm_id'),
                ref_number=sr_data.get('ref_number'),
                title=sr_data.get('title'),
                url=sr_data.get('url'),
                journal=sr_data.get('journal'),
                year=sr_data.get('year'),
            )
            if sr_data.get('created_at'):
                sr.created_at = _parse_datetime_for_sqlite(sr_data['created_at']) or datetime.utcnow()
            db.session.add(sr)
            stats['snippet_references']['added'] += 1

        # ==================== SNIPPET DOCUMENTS ====================
        stats['snippet_documents'] = {'added': 0, 'skipped': 0}
        for sd_data in backup_data.get('snippet_documents', []):
            if not isinstance(sd_data, dict):
                continue
            sd = SnippetDocument(
                algorithm_id=sd_data.get('algorithm_id'),
                title=sd_data.get('title'),
                cloudinary_url=sd_data.get('cloudinary_url'),
                cloudinary_public_id=sd_data.get('cloudinary_public_id'),
                file_type=sd_data.get('file_type'),
                file_size_kb=sd_data.get('file_size_kb'),
                uploaded_by_user_id=user_id_map.get(sd_data.get('uploaded_by_user_id')),
            )
            if sd_data.get('created_at'):
                sd.created_at = _parse_datetime_for_sqlite(sd_data['created_at']) or datetime.utcnow()
            db.session.add(sd)
            stats['snippet_documents']['added'] += 1

        # ==================== SNIPPET IMAGES ====================
        stats['snippet_images'] = {'added': 0, 'skipped': 0}
        for si_data in backup_data.get('snippet_images', []):
            if not isinstance(si_data, dict):
                continue
            si = SnippetImage(
                algorithm_id=si_data.get('algorithm_id'),
                source_url=si_data.get('source_url'),
                source_domain=si_data.get('source_domain'),
                thumbnail_url=si_data.get('thumbnail_url'),
                image_type=si_data.get('image_type'),
                modality=si_data.get('modality'),
                description=si_data.get('description'),
                display_order=si_data.get('display_order', 0),
                license=si_data.get('license'),
                attribution=si_data.get('attribution'),
                added_by_user_id=user_id_map.get(si_data.get('added_by_user_id')),
            )
            if si_data.get('created_at'):
                si.created_at = _parse_datetime_for_sqlite(si_data['created_at']) or datetime.utcnow()
            db.session.add(si)
            stats['snippet_images']['added'] += 1

        # ==================== MDT MEETINGS ====================
        stats['mdt_meetings'] = {'added': 0, 'skipped': 0}
        for mm_data in backup_data.get('mdt_meetings', []):
            if not isinstance(mm_data, dict):
                continue
            mm = MdtMeeting(
                user_id=user_id_map.get(mm_data.get('user_id')),
                name=mm_data.get('name', ''),
                mdt_type=mm_data.get('mdt_type'),
                is_recurring=mm_data.get('is_recurring', False),
            )
            if mm_data.get('date'):
                try:
                    from datetime import date as date_type
                    mm.date = date_type.fromisoformat(mm_data['date'])
                except (ValueError, TypeError):
                    pass
            if mm_data.get('created_at'):
                mm.created_at = _parse_datetime_for_sqlite(mm_data['created_at']) or datetime.utcnow()
            if mm_data.get('updated_at'):
                mm.updated_at = _parse_datetime_for_sqlite(mm_data['updated_at'])
            db.session.add(mm)
            stats['mdt_meetings']['added'] += 1

        # ==================== MDT CASES ====================
        stats['mdt_cases'] = {'added': 0, 'skipped': 0}
        for mc_data in backup_data.get('mdt_cases', []):
            if not isinstance(mc_data, dict):
                continue
            mc = MdtCase(
                user_id=user_id_map.get(mc_data.get('user_id')),
                meeting_id=mc_data.get('meeting_id'),
                case_reference=mc_data.get('case_reference'),
                diagnosis=mc_data.get('diagnosis'),
                status=mc_data.get('status', 'pending'),
                clinical_history=mc_data.get('clinical_history'),
                imaging_findings=mc_data.get('imaging_findings'),
                histology_biopsy=mc_data.get('histology_biopsy'),
                lab_values=mc_data.get('lab_values'),
                additional_notes=mc_data.get('additional_notes'),
                pre_mdt_summary=mc_data.get('pre_mdt_summary'),
                mdt_consensus=mc_data.get('mdt_consensus'),
                action_plan=mc_data.get('action_plan'),
                linked_case_id=mc_data.get('linked_case_id'),
                source_smart_reporter_session_id=mc_data.get('source_smart_reporter_session_id'),
            )
            if mc_data.get('follow_up_date'):
                try:
                    from datetime import date as date_type
                    mc.follow_up_date = date_type.fromisoformat(mc_data['follow_up_date'])
                except (ValueError, TypeError):
                    pass
            if mc_data.get('created_at'):
                mc.created_at = _parse_datetime_for_sqlite(mc_data['created_at']) or datetime.utcnow()
            if mc_data.get('updated_at'):
                mc.updated_at = _parse_datetime_for_sqlite(mc_data['updated_at'])
            db.session.add(mc)
            stats['mdt_cases']['added'] += 1

        # ==================== OSCE GUIDE ====================
        stats['osce_cases'] = {'added': 0, 'skipped': 0}
        for oc_data in backup_data.get('osce_cases', []):
            if not isinstance(oc_data, dict):
                continue
            oc = OsceCase(
                code=oc_data.get('code', ''),
                diagnosis=oc_data.get('diagnosis', ''),
                modality=oc_data.get('modality', ''),
                category=oc_data.get('category', ''),
                difficulty=oc_data.get('difficulty', 'Moderate'),
                osce_data=oc_data.get('osce_data'),
                content_html=oc_data.get('content_html'),
                linked_case_id=oc_data.get('linked_case_id'),
                linked_case_ids=oc_data.get('linked_case_ids'),
                reference_links=oc_data.get('reference_links'),
                is_published=oc_data.get('is_published', False),
                sort_order=oc_data.get('sort_order', 0),
            )
            if oc_data.get('created_at'):
                oc.created_at = _parse_datetime_for_sqlite(oc_data['created_at']) or datetime.utcnow()
            if oc_data.get('updated_at'):
                oc.updated_at = _parse_datetime_for_sqlite(oc_data['updated_at'])
            db.session.add(oc)
            stats['osce_cases']['added'] += 1

        stats['osce_case_images'] = {'added': 0, 'skipped': 0}
        for oi_data in backup_data.get('osce_case_images', []):
            if not isinstance(oi_data, dict):
                continue
            oi = OsceCaseImage(
                osce_case_id=oi_data.get('osce_case_id'),
                image_url=oi_data.get('image_url', ''),
                image_public_id=oi_data.get('image_public_id'),
                image_thumbnail_url=oi_data.get('image_thumbnail_url'),
                image_description=oi_data.get('image_description', ''),
                attribution=oi_data.get('attribution', ''),
                source_url=oi_data.get('source_url'),
                is_annotated=oi_data.get('is_annotated', False),
                paired_image_id=oi_data.get('paired_image_id'),
                sort_order=oi_data.get('sort_order', 0),
            )
            if oi_data.get('created_at'):
                oi.created_at = _parse_datetime_for_sqlite(oi_data['created_at']) or datetime.utcnow()
            db.session.add(oi)
            stats['osce_case_images']['added'] += 1

        # ==================== AUDIT & COMPLIANCE ====================
        stats['pii_override_logs'] = {'added': 0, 'skipped': 0}
        for pol_data in backup_data.get('pii_override_logs', []):
            if not isinstance(pol_data, dict):
                continue
            pol = PiiOverrideLog(
                user_id=user_id_map.get(pol_data.get('user_id')),
                action=pol_data.get('action'),
                flagged_types=pol_data.get('flagged_types'),
                flagged_count=pol_data.get('flagged_count'),
                target_url=pol_data.get('target_url'),
            )
            if pol_data.get('created_at'):
                pol.created_at = _parse_datetime_for_sqlite(pol_data['created_at']) or datetime.utcnow()
            db.session.add(pol)
            stats['pii_override_logs']['added'] += 1

        stats['erasure_logs'] = {'added': 0, 'skipped': 0}
        for el_data in backup_data.get('erasure_logs', []):
            if not isinstance(el_data, dict):
                continue
            el = ErasureLog(
                erasure_type=el_data.get('erasure_type'),
                initiated_by_user_id=el_data.get('initiated_by_user_id'),
                target_user_email_hash=el_data.get('target_user_email_hash'),
                records_deleted=el_data.get('records_deleted'),
            )
            if el_data.get('created_at'):
                el.created_at = _parse_datetime_for_sqlite(el_data['created_at']) or datetime.utcnow()
            db.session.add(el)
            stats['erasure_logs']['added'] += 1

        stats['admin_action_logs'] = {'added': 0, 'skipped': 0}
        for aal_data in backup_data.get('admin_action_logs', []):
            if not isinstance(aal_data, dict):
                continue
            aal = AdminActionLog(
                user_id=user_id_map.get(aal_data.get('user_id')),
                action=aal_data.get('action'),
                target_type=aal_data.get('target_type'),
                target_id=aal_data.get('target_id'),
                details=aal_data.get('details'),
                ip_address=aal_data.get('ip_address'),
            )
            if aal_data.get('created_at'):
                aal.created_at = _parse_datetime_for_sqlite(aal_data['created_at']) or datetime.utcnow()
            db.session.add(aal)
            stats['admin_action_logs']['added'] += 1

        # Final commit for new tables
        try:
            db.session.commit()
            print(f"[IMPORT] New tables imported: {stats.get('related_cases_links', {}).get('added', 0)} related links, {stats.get('case_audit_logs', {}).get('added', 0)} audit logs, {stats.get('case_view_logs', {}).get('added', 0)} view logs, {stats.get('user_qa_progress', {}).get('added', 0)} QA progress, {stats.get('ai_diagnosis_cache', {}).get('added', 0)} AI cache, {stats.get('clinical_protocols', {}).get('added', 0)} protocols, {stats.get('radiology_templates', {}).get('added', 0)} radiology templates, {stats.get('reporting_algorithms', {}).get('added', 0)} reporting algorithms, {stats.get('incidental_finding_calculators', {}).get('added', 0)} IF calculators, {stats.get('content_requests', {}).get('added', 0)} content requests, {stats.get('imported_case_staging', {}).get('added', 0)} staging cases, {stats.get('peer_review_claims', {}).get('added', 0)} peer review claims, {stats.get('admin_documents', {}).get('added', 0)} admin docs, {stats.get('mdt_meetings', {}).get('added', 0)} MDT meetings")
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
        elif 'disturbed' in error_lower or 'request entity too large' in error_lower or 'request body' in error_lower:
            error_message = 'Request body error. The backup file may be too large (Vercel limit: 4.5MB) or the connection was interrupted.'
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
            'original_error': str(e)[:500],
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
        'radiology_templates': RadiologyTemplate.query.count(),
        'reporting_algorithms': ReportingAlgorithm.query.count(),
        'incidental_finding_calculators': IncidentalFindingCalculator.query.count(),
        # New tables (v3.0)
        'vetting_sessions': VettingSession.query.count(),
        'peer_review_claims': PeerReviewClaim.query.count(),
        'admin_documents': AdminDocument.query.count(),
        'radiq_queries': RadIQQuery.query.count(),
        'mdt_meetings': MdtMeeting.query.count(),
        'learning_questions': LearningQuestion.query.count(),
    }
    
    return jsonify({
        'is_admin': True,
        'last_backup_time': last_backup,
        'hours_since_backup': hours_since,
        'needs_backup': needs_backup,
        'stats': stats
    })