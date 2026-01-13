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
                    # Convert case_number to FRCR-Revision format if body_part is available
                    # Format: bodypart-00<number> (e.g., chest-0042, brain-0123)
                    case_number = case_data.get('case_number')
                    body_part = case_data.get('body_part')
                    
                    # If body_part is available, convert case_number format
                    if body_part and case_number:
                        try:
                            # Extract body part name and convert to lowercase short form
                            # Handle both enum values and string values
                            if hasattr(body_part, 'value'):
                                body_part_name = body_part.value.lower()
                            else:
                                body_part_name = str(body_part).lower()
                            
                            body_part_name = body_part_name.replace('_', '').replace(' ', '')
                            # Take first 6 chars for readability
                            body_part_short = body_part_name[:6]
                            
                            # Extract number from case_number (handle both string and int)
                            case_num_str = str(case_number)
                            # Try to extract trailing number
                            import re
                            num_match = re.search(r'(\d+)$', case_num_str)
                            if num_match:
                                num = int(num_match.group(1))
                                # Format as bodypart-00<number>
                                case_number = f"{body_part_short}-{num:03d}"
                            else:
                                # If no number found, use original
                                case_number = str(case_number) if case_number else None
                        except Exception as e:
                            # If conversion fails, keep original as string
                            print(f"[IMPORT] Warning: Could not convert case_number format: {e}")
                            case_number = str(case_data.get('case_number')) if case_data.get('case_number') else None
                    else:
                        # Convert to string even if no body_part
                        case_number = str(case_number) if case_number else None
                    
                    # Convert questions/answers to JSON format if they're lists
                    questions_json = case_data.get('questions', '')
                    if isinstance(questions_json, list):
                        questions_json = json.dumps(questions_json)
                    elif not questions_json:
                        questions_json = '[]'
                    
                    answers_json = case_data.get('answers', '')
                    if isinstance(answers_json, list):
                        answers_json = json.dumps(answers_json)
                    elif not answers_json:
                        answers_json = '[]'
                    
                    # Note: case_number is stored as Integer in ImportedCaseStaging model
                    # We'll convert to string format during promotion
                    # For now, try to extract numeric part if it's a string
                    case_number_int = None
                    if case_number:
                        try:
                            # Extract numeric part from formatted string (e.g., "chest-042" -> 42)
                            import re
                            num_match = re.search(r'(\d+)$', str(case_number))
                            if num_match:
                                case_number_int = int(num_match.group(1))
                            elif str(case_number).isdigit():
                                case_number_int = int(case_number)
                        except (ValueError, AttributeError):
                            pass
                    
                    staging = ImportedCaseStaging(
                        original_id=case_data.get('id'),
                        case_number=case_number_int,  # Store as int (model requirement), format string stored separately
                        diagnosis=case_data.get('diagnosis', ''),
                        questions=questions_json,
                        answers=answers_json,
                        discussion=case_data.get('discussion'),
                        enrichment_status='pending',
                        import_batch_id=import_batch_id,
                        source_system=source_system,
                    )
                    
                    # Store formatted case_number string in enrichment_notes for promotion
                    if case_number and isinstance(case_number, str) and '-' in case_number:
                        if staging.enrichment_notes:
                            staging.enrichment_notes = f"[CASE_NUMBER_FORMATTED]{case_number}[/CASE_NUMBER_FORMATTED]\n{staging.enrichment_notes}"
                        else:
                            staging.enrichment_notes = f"[CASE_NUMBER_FORMATTED]{case_number}[/CASE_NUMBER_FORMATTED]"
                    db.session.add(staging)
                    db.session.flush()  # Get staging ID for image import
                    
                    # Import images if present - store as JSON in enrichment_notes temporarily
                    # Handle both formats:
                    # 1. FRCR Revision: images nested in case_data['images']
                    # 2. FRCR Examiner: images in separate backup_data['case_images'] array
                    old_case_id = case_data.get('id')
                    images_data = case_data.get('images', [])
                    
                    # If no images in case data, check separate case_images array (FRCR Examiner format)
                    if not images_data and 'case_images' in backup_data:
                        print(f"[IMPORT] Looking for images in separate case_images array for case_id={old_case_id}, case_number={case_number}")
                        case_images_list = backup_data.get('case_images', [])
                        print(f"[IMPORT] Total images in backup: {len(case_images_list)}")
                        
                        # Find images matching this case
                        for img_data in case_images_list:
                            if not isinstance(img_data, dict):
                                continue
                            
                            img_case_id = img_data.get('case_id')
                            img_case_number = img_data.get('case_number')
                            
                            # Normalize types for comparison
                            img_case_id_normalized = int(img_case_id) if img_case_id is not None and str(img_case_id).isdigit() else img_case_id
                            old_case_id_normalized = int(old_case_id) if old_case_id is not None and str(old_case_id).isdigit() else old_case_id
                            
                            case_number_str = str(case_number) if case_number else None
                            img_case_number_str = str(img_case_number) if img_case_number else None
                            
                            # Match by case_id or case_number
                            matches = False
                            if old_case_id_normalized is not None and img_case_id_normalized is not None:
                                if img_case_id_normalized == old_case_id_normalized:
                                    matches = True
                                    print(f"[IMPORT] ✓ Matched image by case_id: {old_case_id_normalized}")
                            elif case_number_str and img_case_number_str:
                                if img_case_number_str == case_number_str:
                                    matches = True
                                    print(f"[IMPORT] ✓ Matched image by case_number (exact): {case_number_str}")
                                elif case_number_str.isdigit() and img_case_number_str.isdigit():
                                    if int(case_number_str) == int(img_case_number_str):
                                        matches = True
                                        print(f"[IMPORT] ✓ Matched image by case_number (numeric): {case_number_str}")
                            
                            if matches:
                                images_data.append(img_data)
                    
                    if images_data:
                        import base64
                        
                        # Store images as JSON in enrichment_notes (temporary until we add proper field)
                        images_json = []
                        for img_data in images_data:
                            try:
                                if not isinstance(img_data, dict):
                                    continue
                                
                                # Support both field name formats
                                image_filename = img_data.get('image_filename') or img_data.get('filename', 'image')
                                image_description = img_data.get('image_description') or img_data.get('description', '')
                                image_type = img_data.get('image_type', 'image/jpeg')
                                image_data_base64 = img_data.get('image_data')
                                
                                if image_data_base64:
                                    # Store base64 encoded image data
                                    images_json.append({
                                        'filename': image_filename,
                                        'image_type': image_type,
                                        'description': image_description,
                                        'image_data': image_data_base64  # Keep as base64 string
                                    })
                                    print(f"[IMPORT] Added image to staging: {image_filename} (data length: {len(image_data_base64)})")
                                else:
                                    print(f"[IMPORT] Warning: Image {image_filename} has no image_data")
                            except Exception as img_err:
                                print(f"[IMPORT] Warning: Failed to process image for case {case_number}: {img_err}")
                                errors.append(f"Failed to process image for case {case_number}: {str(img_err)}")
                        
                        # Store images JSON in enrichment_notes with special marker
                        if images_json:
                            images_json_str = json.dumps(images_json)
                            if staging.enrichment_notes:
                                staging.enrichment_notes = f"[IMAGES_JSON]{images_json_str}[/IMAGES_JSON]\n{staging.enrichment_notes}"
                            else:
                                staging.enrichment_notes = f"[IMAGES_JSON]{images_json_str}[/IMAGES_JSON]"
                            
                            # Explicitly mark the object as modified
                            from sqlalchemy.orm.attributes import flag_modified
                            flag_modified(staging, 'enrichment_notes')
                            
                            print(f"[IMPORT] ✓ Stored {len(images_json)} images in staging case {staging.id} enrichment_notes")
                        else:
                            print(f"[IMPORT] ⚠️ No images to store for staging case {staging.id}")
                    else:
                        print(f"[IMPORT] ⚠️ No images found for case (case_id={old_case_id}, case_number={case_number})")
                    
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
    def promote_case(staging_case_id, created_by_user_id=None, target_status=None):
        """
        Promote enriched case from staging to production
        
        Args:
            staging_case_id: ID of ImportedCaseStaging record
            created_by_user_id: User ID creating the case
            target_status: CaseStatus enum value (default: PUBLISHED if is_public, else DRAFT)
            
        Returns:
            {success, message, case_id}
        """
        try:
            staging = ImportedCaseStaging.query.get(staging_case_id)
            if not staging:
                return {'success': False, 'message': 'Staging case not found'}
            
            # Allow promotion if enriched (approval can be bypassed for direct enrich-and-promote)
            if staging.enrichment_status != 'enriched':
                return {
                    'success': False,
                    'message': 'Case must be enriched before promotion'
                }
            
            # Convert case_number to proper format if needed
            case_number = staging.case_number
            
            # Check if formatted case_number is stored in enrichment_notes
            import re
            formatted_match = re.search(r'\[CASE_NUMBER_FORMATTED\](.*?)\[/CASE_NUMBER_FORMATTED\]', staging.enrichment_notes or '', re.DOTALL)
            if formatted_match:
                case_number = formatted_match.group(1).strip()
            elif staging.body_part:
                # Ensure case_number is in format: bodypart-00<number>
                if isinstance(case_number, int) or (isinstance(case_number, str) and case_number.isdigit()):
                    # Extract number
                    num = int(case_number) if isinstance(case_number, str) else case_number
                    # Get body part short name
                    body_part_name = staging.body_part.value.lower().replace('_', '').replace(' ', '')
                    body_part_short = body_part_name[:6]
                    # Format as bodypart-00<number>
                    case_number = f"{body_part_short}-{num:03d}"
                elif isinstance(case_number, str) and '-' not in case_number:
                    # If it's a string without dash, try to format it
                    try:
                        num = int(case_number)
                        body_part_name = staging.body_part.value.lower().replace('_', '').replace(' ', '')
                        body_part_short = body_part_name[:6]
                        case_number = f"{body_part_short}-{num:03d}"
                    except ValueError:
                        pass  # Keep original if conversion fails
            else:
                # Convert to string if it's an integer
                case_number = str(case_number) if case_number else None
            
            # Create production case
            # Legacy questions/answers columns removed - data migrated to Question/Answer tables below
            case = Case(
                case_number=case_number,
                diagnosis=staging.diagnosis,
                discussion=staging.discussion,
                module=staging.module,
                body_part=staging.body_part,
                age_group=staging.age_group,
                is_public=staging.is_public,
                status=target_status if target_status else (CaseStatus.PUBLISHED if staging.is_public else CaseStatus.DRAFT),
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
            
            # Migrate images if stored in enrichment_notes (temporary storage)
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
                                        case_id=case.id,
                                        image_filename=img_data.get('filename', 'image'),
                                        image_type=img_data.get('image_type', 'image/jpeg'),
                                        image_description=img_data.get('description', ''),
                                        image_data=image_data_binary
                                    )
                                    db.session.add(case_image)
                            except Exception as img_err:
                                print(f"[PROMOTION] Warning: Failed to migrate image: {img_err}")
                    except (json.JSONDecodeError, Exception) as e:
                        print(f"[PROMOTION] Warning: Could not parse images JSON: {e}")
            
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
