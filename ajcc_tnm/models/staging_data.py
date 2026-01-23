"""
AJCCStagingData Model

Stores TNM staging data with structured JSON and optional HTML sections.
"""

import json
from datetime import datetime
from models import db


class AJCCStagingData(db.Model):
    """Stores TNM staging data with structured JSON and optional HTML sections"""
    id = db.Column(db.Integer, primary_key=True)
    disease_site_id = db.Column(db.Integer, db.ForeignKey('ajcc_disease_site.id'), nullable=False, index=True)
    diagnosis_year_id = db.Column(db.Integer, db.ForeignKey('ajcc_diagnosis_year.id'), nullable=False, index=True)
    
    # ============================================
    # PRIMARY DATA: Structured JSON (preferred)
    # ============================================
    
    # Core TNM staging data as clean JSON
    tnm_data_json = db.Column(db.Text, nullable=True)  # Main TNM staging: T, N, M definitions + stage groups
    
    # Additional structured sections as JSON
    cancers_staged_json = db.Column(db.Text, nullable=True)  # List of cancers staged by this system
    cancers_not_staged_json = db.Column(db.Text, nullable=True)  # List of cancers NOT staged
    summary_changes_json = db.Column(db.Text, nullable=True)  # Summary of changes from previous edition
    primary_sites_json = db.Column(db.Text, nullable=True)  # ICD-O codes and primary site descriptions
    histopathologic_types_json = db.Column(db.Text, nullable=True)  # Histopathologic type information
    imaging_workup_json = db.Column(db.Text, nullable=True)  # Clinical staging/imaging workup data
    staging_rules_json = db.Column(db.Text, nullable=True)  # Staging rules and criteria
    common_scenarios_json = db.Column(db.Text, nullable=True)  # Common staging scenarios/examples
    notes_json = db.Column(db.Text, nullable=True)  # Explanatory notes, figures references
    
    # ============================================
    # LEGACY: HTML sections (for backward compatibility)
    # ============================================
    section_1_quick_reference_html = db.Column(db.Text, nullable=True)
    section_2_cancers_staged_html = db.Column(db.Text, nullable=True)
    section_3_cancers_not_staged_html = db.Column(db.Text, nullable=True)
    section_4_summary_changes_html = db.Column(db.Text, nullable=True)
    section_5_primary_site_html = db.Column(db.Text, nullable=True)
    section_6_histopathologic_type_html = db.Column(db.Text, nullable=True)
    section_7_clinical_staging_workup_html = db.Column(db.Text, nullable=True)
    section_8_staging_rules_html = db.Column(db.Text, nullable=True)
    section_9_common_scenarios_html = db.Column(db.Text, nullable=True)
    section_10_explanatory_notes_html = db.Column(db.Text, nullable=True)
    
    # Metadata
    raw_html_content = db.Column(db.Text, nullable=True)  # Store original full page HTML for reference
    extracted_at = db.Column(db.DateTime, default=datetime.utcnow)
    extracted_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    last_updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    data_version = db.Column(db.Integer, default=2)  # 1=HTML only, 2=JSON+HTML
    
    # Relationships
    extracted_by = db.relationship('User', foreign_keys=[extracted_by_user_id], backref='extracted_tnm_data')
    
    # Unique constraint: one staging data record per disease/year combination
    __table_args__ = (
        db.UniqueConstraint('disease_site_id', 'diagnosis_year_id', name='uq_disease_year_staging'),
        db.Index('idx_disease_year', 'disease_site_id', 'diagnosis_year_id'),
    )
    
    def __repr__(self):
        return f'<AJCCStagingData Disease:{self.disease_site_id} Year:{self.diagnosis_year_id}>'
    
    # ============================================
    # JSON Data Access Methods
    # ============================================
    
    def get_tnm_data(self):
        """Get parsed TNM staging data as dict"""
        if self.tnm_data_json:
            try:
                return json.loads(self.tnm_data_json)
            except:
                return None
        return None
    
    def set_tnm_data(self, data):
        """Set TNM staging data from dict"""
        self.tnm_data_json = json.dumps(data, ensure_ascii=False) if data else None
    
    def get_t_definitions(self):
        """Get T stage definitions"""
        tnm = self.get_tnm_data()
        return tnm.get('t_definitions', []) if tnm else []
    
    def get_n_definitions(self):
        """Get N stage definitions (clinical and pathological)"""
        tnm = self.get_tnm_data()
        return tnm.get('n_definitions', {}) if tnm else {}
    
    def get_m_definitions(self):
        """Get M stage definitions"""
        tnm = self.get_tnm_data()
        return tnm.get('m_definitions', []) if tnm else []
    
    def get_stage_groups(self):
        """Get prognostic stage group combinations"""
        tnm = self.get_tnm_data()
        return tnm.get('stage_groups', []) if tnm else []
    
    def get_stage_for_tnm(self, t_stage, n_stage, m_stage):
        """
        Look up the prognostic stage for given T, N, M values.
        
        Args:
            t_stage: T stage value (e.g., "T1", "T2", "T3")
            n_stage: N stage value (e.g., "N0", "N1", "N2")
            m_stage: M stage value (e.g., "M0", "M1")
            
        Returns:
            Stage group string (e.g., "I", "II", "IVA") or None if not found
        """
        stage_groups = self.get_stage_groups()
        
        for sg in stage_groups:
            t_match = self._matches_tnm_pattern(t_stage, sg.get('T', ''))
            n_match = self._matches_tnm_pattern(n_stage, sg.get('N', ''))
            m_match = self._matches_tnm_pattern(m_stage, sg.get('M', ''))
            
            if t_match and n_match and m_match:
                return sg.get('stage')
        
        return None
    
    def _matches_tnm_pattern(self, value, pattern):
        """Check if a TNM value matches a pattern (e.g., "T1" matches "T1, T2, T3" or "Any T")"""
        if not pattern or not value:
            return False
        
        pattern = pattern.strip()
        value = value.strip().upper()
        
        # Handle "Any X" patterns
        if pattern.lower().startswith('any'):
            return True
        
        # Handle comma-separated values
        options = [opt.strip().upper() for opt in pattern.split(',')]
        return value in options
    
    def get_json_section(self, section_name):
        """Get a JSON section by name"""
        section_map = {
            'tnm': self.tnm_data_json,
            'cancers_staged': self.cancers_staged_json,
            'cancers_not_staged': self.cancers_not_staged_json,
            'summary_changes': self.summary_changes_json,
            'primary_sites': self.primary_sites_json,
            'histopathologic_types': self.histopathologic_types_json,
            'imaging_workup': self.imaging_workup_json,
            'staging_rules': self.staging_rules_json,
            'common_scenarios': self.common_scenarios_json,
            'notes': self.notes_json,
        }
        json_str = section_map.get(section_name)
        if json_str:
            try:
                return json.loads(json_str)
            except:
                return None
        return None
    
    def set_json_section(self, section_name, data):
        """Set a JSON section by name"""
        section_map = {
            'tnm': 'tnm_data_json',
            'cancers_staged': 'cancers_staged_json',
            'cancers_not_staged': 'cancers_not_staged_json',
            'summary_changes': 'summary_changes_json',
            'primary_sites': 'primary_sites_json',
            'histopathologic_types': 'histopathologic_types_json',
            'imaging_workup': 'imaging_workup_json',
            'staging_rules': 'staging_rules_json',
            'common_scenarios': 'common_scenarios_json',
            'notes': 'notes_json',
        }
        field_name = section_map.get(section_name)
        if field_name:
            json_str = json.dumps(data, ensure_ascii=False) if data else None
            setattr(self, field_name, json_str)
    
    def to_full_json(self):
        """Export all data as a complete JSON structure"""
        result = {
            'id': self.id,
            'disease_site_id': self.disease_site_id,
            'disease_name': self.disease_site.disease_name if self.disease_site else None,
            'diagnosis_year': self.diagnosis_year.year if self.diagnosis_year else None,
            'extracted_at': self.extracted_at.isoformat() if self.extracted_at else None,
            'data_version': self.data_version,
            'tnm_staging': self.get_tnm_data(),
            'sections': {
                'cancers_staged': self.get_json_section('cancers_staged'),
                'cancers_not_staged': self.get_json_section('cancers_not_staged'),
                'summary_changes': self.get_json_section('summary_changes'),
                'primary_sites': self.get_json_section('primary_sites'),
                'histopathologic_types': self.get_json_section('histopathologic_types'),
                'imaging_workup': self.get_json_section('imaging_workup'),
                'staging_rules': self.get_json_section('staging_rules'),
                'common_scenarios': self.get_json_section('common_scenarios'),
                'notes': self.get_json_section('notes'),
            }
        }
        return result
    
    # ============================================
    # Legacy HTML Methods (backward compatibility)
    # ============================================
    
    def get_section_html(self, section_number):
        """Get HTML content for a specific section (1-10) - LEGACY"""
        section_map = {
            1: self.section_1_quick_reference_html,
            2: self.section_2_cancers_staged_html,
            3: self.section_3_cancers_not_staged_html,
            4: self.section_4_summary_changes_html,
            5: self.section_5_primary_site_html,
            6: self.section_6_histopathologic_type_html,
            7: self.section_7_clinical_staging_workup_html,
            8: self.section_8_staging_rules_html,
            9: self.section_9_common_scenarios_html,
            10: self.section_10_explanatory_notes_html,
        }
        return section_map.get(section_number)
    
    def set_section_html(self, section_number, html_content):
        """Set HTML content for a specific section (1-10) - LEGACY"""
        section_map = {
            1: 'section_1_quick_reference_html',
            2: 'section_2_cancers_staged_html',
            3: 'section_3_cancers_not_staged_html',
            4: 'section_4_summary_changes_html',
            5: 'section_5_primary_site_html',
            6: 'section_6_histopathologic_type_html',
            7: 'section_7_clinical_staging_workup_html',
            8: 'section_8_staging_rules_html',
            9: 'section_9_common_scenarios_html',
            10: 'section_10_explanatory_notes_html',
        }
        field_name = section_map.get(section_number)
        if field_name:
            setattr(self, field_name, html_content)
