"""
Service layer for case import, duplicate detection, and promotion
Handles importing cases from backup JSON files and managing the enrichment workflow
"""
import json
import uuid
from datetime import datetime
from models import db, ImportedCaseStaging, Case, CaseStatus, FRCRModule, BodyPart, AgeGroup, CaseAuditLog


class ImportService:
    """Handles import of cases from backup JSON files into staging"""
    
    @staticmethod
    def import_from_backup(backup_file_path, source_system='frcr_examiner'):
        """
        Import cases from backup JSON file into staging area
        
        Args:
            backup_file_path: Path to .json backup file
            source_system: Source system identifier (default: frcr_examiner)
            
        Returns:
            {
                'success': bool,
                'import_batch_id': str,
                'total_imported': int,
                'errors': [str]
            }
        """
        errors = []
        imported_count = 0
        import_batch_id = str(uuid.uuid4())
        
        try:
            # Read backup file
            with open(backup_file_path, 'r') as f:
                backup_data = json.load(f)
            
            # Extract cases
            cases_data = backup_data.get('cases', [])
            
            for case_data in cases_data:
                try:
                    staging = ImportedCaseStaging(
                        original_id=case_data.get('id'),
                        case_number=case_data.get('case_number'),
                        diagnosis=case_data.get('diagnosis', ''),
                        questions=case_data.get('questions', ''),
                        answers=case_data.get('answers', ''),
                        discussion=case_data.get('discussion'),
                        enrichment_status='pending',
                        import_batch_id=import_batch_id,
                        source_system=source_system,
                    )
                    db.session.add(staging)
                    imported_count += 1
                except Exception as e:
                    errors.append(f"Failed to import case {case_data.get('case_number')}: {str(e)}")
            
            db.session.commit()
            
            return {
                'success': True,
                'import_batch_id': import_batch_id,
                'total_imported': imported_count,
                'errors': errors
            }
            
        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'import_batch_id': None,
                'total_imported': 0,
                'errors': [str(e)]
            }
    
    @staticmethod
    def get_pending_cases(page=1, per_page=20):
        """Get paginated list of cases pending enrichment"""
        return ImportedCaseStaging.query.filter_by(
            enrichment_status='pending'
        ).paginate(page=page, per_page=per_page)
    
    @staticmethod
    def get_import_batch(batch_id):
        """Get all cases from a specific import batch"""
        return ImportedCaseStaging.query.filter_by(
            import_batch_id=batch_id
        ).all()
    
    @staticmethod
    def get_enrichment_stats(batch_id=None):
        """Get statistics on enrichment progress"""
        query = ImportedCaseStaging.query
        
        if batch_id:
            query = query.filter_by(import_batch_id=batch_id)
        
        total = query.count()
        by_status = {
            'pending': query.filter_by(enrichment_status='pending').count(),
            'enriched': query.filter_by(enrichment_status='enriched').count(),
            'rejected': query.filter_by(enrichment_status='rejected').count(),
            'promoted': query.filter_by(enrichment_status='promoted').count(),
        }
        
        return {
            'total': total,
            'by_status': by_status,
            'completion_percentage': int((by_status['enriched'] / total * 100)) if total > 0 else 0
        }


class DuplicateDetectionService:
    """Detects and handles duplicate cases during import"""
    
    @staticmethod
    def check_duplicates(backup_data, source_system='frcr_examiner'):
        """
        Analyze backup for duplicates against existing data
        
        Returns: {
            'total_cases': int,
            'new_cases': [...],
            'duplicates_in_staging': [...],
            'duplicates_in_production': [...],
            'conflicts': [...]
        }
        """
        duplicates_in_staging = []
        duplicates_in_production = []
        new_cases = []
        
        for case_data in backup_data.get('cases', []):
            original_id = case_data.get('id')
            diagnosis = case_data.get('diagnosis', '')
            
            # Check if in staging
            staging_case = ImportedCaseStaging.query.filter_by(
                source_system=source_system,
                original_id=original_id
            ).filter(
                ImportedCaseStaging.is_replacement == False
            ).first()
            
            if staging_case:
                duplicates_in_staging.append({
                    'original_id': original_id,
                    'staging_id': staging_case.id,
                    'diagnosis': diagnosis,
                    'import_batch_id': staging_case.import_batch_id,
                    'enrichment_status': staging_case.enrichment_status,
                    'imported_at': staging_case.import_timestamp.isoformat(),
                })
                continue
            
            # Check if already in production
            production_case = Case.query.join(
                ImportedCaseStaging
            ).filter(
                ImportedCaseStaging.source_system == source_system,
                ImportedCaseStaging.original_id == original_id,
                Case.id == ImportedCaseStaging.promoted_to_case_id
            ).first()
            
            if production_case:
                duplicates_in_production.append({
                    'original_id': original_id,
                    'case_id': production_case.id,
                    'diagnosis': diagnosis,
                    'module': production_case.module.value if production_case.module else None,
                    'promoted_at': (
                        ImportedCaseStaging.query.filter_by(
                            promoted_to_case_id=production_case.id
                        ).first().promoted_at.isoformat() if production_case else None
                    ),
                })
                continue
            
            # New case
            new_cases.append({
                'original_id': original_id,
                'case_number': case_data.get('case_number'),
                'diagnosis': diagnosis[:100] if diagnosis else '',
            })
        
        return {
            'total_cases': len(backup_data.get('cases', [])),
            'new_cases': new_cases,
            'duplicates_in_staging': duplicates_in_staging,
            'duplicates_in_production': duplicates_in_production,
            'new_count': len(new_cases),
            'staging_count': len(duplicates_in_staging),
            'production_count': len(duplicates_in_production),
        }
    
    @staticmethod
    def get_duplicate_conflicts(original_id, source_system='frcr_examiner'):
        """Get all versions of a case (staging + production)"""
        staging = ImportedCaseStaging.query.filter_by(
            source_system=source_system,
            original_id=original_id,
            is_replacement=False
        ).all()
        
        production = Case.query.join(
            ImportedCaseStaging
        ).filter(
            ImportedCaseStaging.source_system == source_system,
            ImportedCaseStaging.original_id == original_id,
            Case.id == ImportedCaseStaging.promoted_to_case_id
        ).all()
        
        return {
            'staging_versions': [{
                'id': s.id,
                'batch_id': s.import_batch_id,
                'enrichment_status': s.enrichment_status,
                'imported_at': s.import_timestamp.isoformat(),
                'enriched_by': s.enriched_by.full_name if s.enriched_by else None,
            } for s in staging],
            'production_version': {
                'id': production[0].id if production else None,
                'module': production[0].module.value if production and production[0].module else None,
                'promoted_at': (
                    ImportedCaseStaging.query.filter_by(
                        promoted_to_case_id=production[0].id
                    ).first().promoted_at.isoformat() if production else None
                )
            } if production else None,
        }


class ConflictResolutionService:
    """Handles admin decisions on duplicate imports"""
    
    # Resolution strategies
    SKIP = 'skip'
    REPLACE_STAGING = 'replace'
    UPDATE_PRODUCTION = 'update'
    CREATE_NEW = 'create_new'
    FORCE_IMPORT = 'force_import'
    
    @staticmethod
    def resolve_duplicate(original_id, new_case_data, resolution_strategy, user_id):
        """
        Handle duplicate based on admin's choice
        
        Args:
            original_id: ID from source system
            new_case_data: New case data from backup
            resolution_strategy: skip|replace|update|create_new|force_import
            user_id: Admin user ID making the decision
        
        Returns: {success, message, staging_id, action}
        """
        
        if resolution_strategy == ConflictResolutionService.SKIP:
            return {
                'success': True,
                'message': 'Case skipped',
                'action': 'skip',
            }
        
        elif resolution_strategy == ConflictResolutionService.REPLACE_STAGING:
            # Find existing staging case and mark as replaced
            existing = ImportedCaseStaging.query.filter_by(
                original_id=original_id,
                is_replacement=False
            ).order_by(ImportedCaseStaging.import_timestamp.desc()).first()
            
            if not existing:
                return {'success': False, 'message': 'No staging case found to replace'}
            
            # Create new version
            new_staging = ImportedCaseStaging(
                original_id=new_case_data['id'],
                case_number=new_case_data.get('case_number'),
                diagnosis=new_case_data.get('diagnosis', ''),
                questions=new_case_data.get('questions', ''),
                answers=new_case_data.get('answers', ''),
                discussion=new_case_data.get('discussion'),
                import_batch_id=existing.import_batch_id,
                previous_staging_id=existing.id,
                is_replacement=True,
                enrichment_status='pending',
                source_system='frcr_examiner',
            )
            
            db.session.add(new_staging)
            db.session.commit()
            
            return {
                'success': True,
                'message': f'Case replaced. Previous version (ID:{existing.id}) marked as superseded',
                'action': 'replaced',
                'staging_id': new_staging.id,
                'previous_staging_id': existing.id,
            }
        
        elif resolution_strategy == ConflictResolutionService.UPDATE_PRODUCTION:
            # Find production case and update it
            staging_with_production = ImportedCaseStaging.query.filter_by(
                original_id=original_id
            ).filter(ImportedCaseStaging.promoted_to_case_id != None).first()
            
            if not staging_with_production:
                return {'success': False, 'message': 'No production case found'}
            
            production_case = Case.query.get(staging_with_production.promoted_to_case_id)
            
            # Update production case with new data
            # Legacy questions/answers columns removed - data stored in Question/Answer tables only
            production_case.diagnosis = new_case_data.get('diagnosis', '')
            production_case.discussion = new_case_data.get('discussion')
            production_case.updated_at = datetime.utcnow()
            
            # Create audit log
            CaseAuditLog(
                case_id=production_case.id,
                user_id=user_id,
                action='updated_from_import',
                changes={
                    'diagnosis': new_case_data.get('diagnosis'),
                },
                notes=f'Case data updated from reimport of original_id {original_id}'
            )
            
            db.session.commit()
            
            return {
                'success': True,
                'message': f'Production case {production_case.id} updated',
                'action': 'updated',
                'case_id': production_case.id,
            }
        
        elif resolution_strategy == ConflictResolutionService.CREATE_NEW:
            # Create as completely new case
            new_staging = ImportedCaseStaging(
                original_id=new_case_data['id'],
                case_number=new_case_data.get('case_number'),
                diagnosis=new_case_data.get('diagnosis', ''),
                questions=new_case_data.get('questions', ''),
                answers=new_case_data.get('answers', ''),
                discussion=new_case_data.get('discussion'),
                enrichment_status='pending',
                source_system='frcr_examiner',
                import_batch_id=str(uuid.uuid4()),
            )
            
            db.session.add(new_staging)
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Case imported as new duplicate (treated as separate case)',
                'action': 'created_new',
                'staging_id': new_staging.id,
            }
        
        elif resolution_strategy == ConflictResolutionService.FORCE_IMPORT:
            # Import regardless
            new_staging = ImportedCaseStaging(
                original_id=new_case_data['id'],
                case_number=new_case_data.get('case_number'),
                diagnosis=new_case_data.get('diagnosis', ''),
                questions=new_case_data.get('questions', ''),
                answers=new_case_data.get('answers', ''),
                discussion=new_case_data.get('discussion'),
                enrichment_status='pending',
                source_system='frcr_examiner',
                import_batch_id=str(uuid.uuid4()),
            )
            
            db.session.add(new_staging)
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Case force imported (duplicate of existing case)',
                'action': 'force_imported',
                'staging_id': new_staging.id,
            }
        
        return {
            'success': False,
            'message': 'Unknown resolution strategy',
        }


class PromotionService:
    """Handles promotion of enriched cases from staging to production"""
    
    @staticmethod
    def promote_case(staging_case_id, created_by_user_id=None):
        """
        Promote enriched case from staging to production
        
        Args:
            staging_case_id: ID of ImportedCaseStaging record
            created_by_user_id: User ID creating the case
            
        Returns:
            {success, message, case_id}
        """
        try:
            staging = ImportedCaseStaging.query.get(staging_case_id)
            if not staging:
                return {'success': False, 'message': 'Staging case not found'}
            
            if staging.enrichment_status != 'enriched' or not staging.approved_at:
                return {
                    'success': False,
                    'message': 'Case must be enriched and approved before promotion'
                }
            
            # Create production case
            # Legacy questions/answers columns removed - data migrated to Question/Answer tables below
            case = Case(
                case_number=staging.case_number,
                diagnosis=staging.diagnosis,
                discussion=staging.discussion,
                module=staging.module,
                body_part=staging.body_part,
                age_group=staging.age_group,
                is_public=staging.is_public,
                status=CaseStatus.PUBLISHED if staging.is_public else CaseStatus.DRAFT,
                created_by_user_id=created_by_user_id,
            )
            
            db.session.add(case)
            db.session.flush()
            
            # Migrate Q&A data from staging legacy fields to Question/Answer tables
            # (if staging has legacy JSON data, parse and migrate it)
            import json
            from models import Question, Answer
            
            try:
                if staging.questions and staging.questions != '[]':
                    questions_data = json.loads(staging.questions) if isinstance(staging.questions, str) else staging.questions
                    if isinstance(questions_data, list):
                        for idx, q_data in enumerate(questions_data, start=1):
                            question_text = q_data.get('question_text', '') if isinstance(q_data, dict) else str(q_data)
                            if question_text and question_text.strip():
                                question = Question(
                                    case_id=case.id,
                                    question_number=idx,
                                    question_text=question_text.strip()
                                )
                                db.session.add(question)
            except (json.JSONDecodeError, AttributeError, TypeError) as e:
                print(f"[PROMOTION] Warning: Could not parse staging questions: {e}")
            
            try:
                if staging.answers and staging.answers != '[]':
                    answers_data = json.loads(staging.answers) if isinstance(staging.answers, str) else staging.answers
                    if isinstance(answers_data, list):
                        for idx, a_data in enumerate(answers_data, start=1):
                            answer_text = a_data.get('answer_text', '') if isinstance(a_data, dict) else str(a_data)
                            if answer_text and answer_text.strip():
                                answer = Answer(
                                    case_id=case.id,
                                    answer_number=idx,
                                    answer_text=answer_text.strip()
                                )
                                db.session.add(answer)
            except (json.JSONDecodeError, AttributeError, TypeError) as e:
                print(f"[PROMOTION] Warning: Could not parse staging answers: {e}")
            
            # Update staging record
            staging.promoted_to_case_id = case.id
            staging.promoted_at = datetime.utcnow()
            staging.enrichment_status = 'promoted'
            
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Case promoted to production',
                'case_id': case.id
            }
            
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    def bulk_promote(batch_id, created_by_user_id):
        """Promote all approved cases from a batch"""
        staging_cases = ImportedCaseStaging.query.filter_by(
            import_batch_id=batch_id,
            enrichment_status='enriched'
        ).filter(ImportedCaseStaging.approved_at != None).all()
        
        promoted = 0
        errors = []
        
        for staging in staging_cases:
            result = PromotionService.promote_case(
                staging.id,
                created_by_user_id=created_by_user_id
            )
            if result['success']:
                promoted += 1
            else:
                errors.append(result['message'])
        
        return {
            'promoted': promoted,
            'total_approved': len(staging_cases),
            'errors': errors
        }
