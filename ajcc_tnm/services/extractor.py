"""
AJCC TNM Extraction Service

Extracts TNM staging data from AJCC website API.
Parses HTML content into clean structured JSON.
"""

import json
import os
import re
from datetime import datetime
from typing import Optional, Dict, List, Any
from bs4 import BeautifulSoup, Tag, NavigableString
# Import from module's auth service
from .auth_service import get_ajcc_session

# Import from main app's models (kept in main app for shared use)
from models import db, AJCCStagingData, AJCCDiseaseSite, AJCCDiagnosisYear


class TNMDataCleaner:
    """Cleans and parses AJCC HTML into structured JSON."""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Remove extra whitespace and DITA metadata junk from text."""
        if not text:
            return ""
        # Remove DITA path junk like [/concept/Tdefinition/...] and {""}) 
        text = re.sub(r'\[/concept/[^\]]+', '', text)
        text = re.sub(r'\{["\s]*\}\s*\)', '', text)
        text = re.sub(r'\(validvalue\]', '', text)
        text = re.sub(r'\[validvalue\]', '', text)
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    @staticmethod
    def extract_tnm_value(cell_html: str) -> str:
        """Extract the actual TNM value (TX, T1, N0, M1, etc.) from messy cell HTML."""
        soup = BeautifulSoup(cell_html, 'html.parser')
        text = soup.get_text()
        
        # Try to find the TNM code pattern - it's usually between ") " and " ("
        tnm_patterns = [
            r'\)\s*(Tis)\s*\(',                 # Tis specifically (carcinoma in situ)
            r'\)\s*(TX)\s*\(',                  # TX specifically
            r'\)\s*(T[0-4][ab]?)\s*\(',         # T categories
            r'\)\s*(N[X0-3][abc]?)\s*\(',       # N categories
            r'\)\s*(M[01X])\s*\(',              # M categories
            r'\b(Tis)\b',                        # Fallback for Tis
            r'\b(TX|T[0-4][ab]?)\b',             # Fallback for T
            r'\b(NX|N[0-3][abc]?)\b',            # Fallback for N
            r'\b(MX|M[01])\b',                   # Fallback for M
        ]
        
        for pattern in tnm_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        cleaned = TNMDataCleaner.clean_text(text)
        return cleaned if len(cleaned) < 10 else ""
    
    @staticmethod
    def parse_tnm_table(table_soup, table_type: str = 'T') -> List[Dict[str, str]]:
        """Parse a T, N, or M definition table into structured data."""
        rows = []
        for tr in table_soup.find_all('tr', class_='TNMrow'):
            category_td = tr.find('td', class_='AJCCcategory')
            criteria_td = tr.find('td', class_='AJCCcriteria')
            
            if category_td and criteria_td:
                category = TNMDataCleaner.extract_tnm_value(str(category_td))
                criteria_soup = BeautifulSoup(str(criteria_td), 'html.parser')
                criteria = TNMDataCleaner.clean_text(criteria_soup.get_text())
                
                rows.append({
                    'category': category,
                    'criteria': criteria
                })
        
        return rows
    
    @staticmethod
    def parse_stage_group_table(table_soup) -> List[Dict[str, str]]:
        """Parse the stage group table into structured data."""
        rows = []
        for tr in table_soup.find_all('tr', class_='stagerow'):
            t_val = tr.find('td', class_='Tvalue')
            n_val = tr.find('td', class_='Nvalue')
            m_val = tr.find('td', class_='Mvalue')
            stage = tr.find('td', class_='stagegroup')
            
            if all([t_val, n_val, m_val, stage]):
                rows.append({
                    'T': TNMDataCleaner.clean_text(t_val.get_text()),
                    'N': TNMDataCleaner.clean_text(n_val.get_text()),
                    'M': TNMDataCleaner.clean_text(m_val.get_text()),
                    'stage': TNMDataCleaner.clean_text(stage.get_text())
                })
        
        return rows
    
    @staticmethod
    def parse_quick_reference_to_json(html: str) -> Dict[str, Any]:
        """Parse Quick Reference HTML into structured JSON."""
        soup = BeautifulSoup(html, 'html.parser')
        
        result = {
            'title': '',
            't_definitions': [],
            'n_definitions': {
                'clinical': [],
                'pathological': []
            },
            'm_definitions': [],
            'stage_groups': [],
            'notes': []
        }
        
        # Get title
        title_elem = soup.find('h1')
        if title_elem:
            result['title'] = TNMDataCleaner.clean_text(title_elem.get_text())
        
        # Parse T definitions (may have multiple subsites)
        t_articles = soup.find_all('article', class_='Tdefinition')
        for article in t_articles:
            heading = article.find(['h2', 'h3'])
            subsite_name = TNMDataCleaner.clean_text(heading.get_text()) if heading else 'Unknown'
            # Clean up the heading
            subsite_name = re.sub(r'^\*?Definition of Primary Tumor \(T\)\s*(\(Note T\)\s*)?', '', subsite_name)
            
            table = article.find('table', class_='Ttable')
            if table:
                t_data = TNMDataCleaner.parse_tnm_table(table, 'T')
                result['t_definitions'].append({
                    'subsite': subsite_name.strip() or 'Default',
                    'categories': t_data
                })
        
        # Parse N definitions (clinical and pathological)
        n_articles = soup.find_all('article', class_='Ndefinition')
        for article in n_articles:
            heading = article.find(['h2', 'h3'])
            heading_text = heading.get_text() if heading else ''
            
            table = article.find('table', class_='Ntable')
            if table:
                n_data = TNMDataCleaner.parse_tnm_table(table, 'N')
                if 'pN' in heading_text or 'pathological' in heading_text.lower():
                    result['n_definitions']['pathological'] = n_data
                else:
                    result['n_definitions']['clinical'] = n_data
            
            # Extract notes
            for note in article.find_all('div', class_='note'):
                note_text = TNMDataCleaner.clean_text(note.get_text())
                if note_text and note_text not in result['notes']:
                    result['notes'].append(note_text)
        
        # Parse M definitions
        m_articles = soup.find_all('article', class_='Mdefinition')
        for article in m_articles:
            table = article.find('table', class_='Mtable')
            if table:
                result['m_definitions'] = TNMDataCleaner.parse_tnm_table(table, 'M')
        
        # Parse stage group table
        stage_section = soup.find('article', class_='stagesection')
        if stage_section:
            table = stage_section.find('table', class_='stagetable')
            if table:
                result['stage_groups'] = TNMDataCleaner.parse_stage_group_table(table)
        
        return result
    
    @staticmethod
    def parse_cancers_staged_to_json(html: str) -> Dict[str, Any]:
        """Parse Cancers Staged section to JSON."""
        soup = BeautifulSoup(html, 'html.parser')
        result = {
            'title': 'Cancers Staged Using This Staging System',
            'cancers': [],
            'text': TNMDataCleaner.clean_text(soup.get_text())
        }
        
        # Try to find list items or table rows
        for li in soup.find_all('li'):
            result['cancers'].append(TNMDataCleaner.clean_text(li.get_text()))
        
        return result
    
    @staticmethod
    def parse_cancers_not_staged_to_json(html: str) -> Dict[str, Any]:
        """Parse Cancers Not Staged section to JSON."""
        soup = BeautifulSoup(html, 'html.parser')
        result = {
            'title': 'Cancers Not Staged Using This Staging System',
            'exclusions': []
        }
        
        # Parse table if present
        table = soup.find('table', class_='notstagedtable')
        if table:
            for tr in table.find_all('tr'):
                tds = tr.find_all('td')
                if len(tds) >= 2:
                    result['exclusions'].append({
                        'cancer_type': TNMDataCleaner.clean_text(tds[0].get_text()),
                        'staged_according_to': TNMDataCleaner.clean_text(tds[1].get_text())
                    })
        
        return result
    
    @staticmethod
    def parse_summary_changes_to_json(html: str) -> Dict[str, Any]:
        """Parse Summary of Changes section to JSON."""
        soup = BeautifulSoup(html, 'html.parser')
        result = {
            'title': 'Summary of Changes',
            'changes': []
        }
        
        # Parse changes table
        table = soup.find('table', class_='changestable')
        if table:
            for tr in table.find_all('tr'):
                tds = tr.find_all('td')
                if len(tds) >= 2:
                    change = {
                        'change': TNMDataCleaner.clean_text(tds[0].get_text()),
                        'details': TNMDataCleaner.clean_text(tds[1].get_text())
                    }
                    if len(tds) >= 3:
                        change['level_of_evidence'] = TNMDataCleaner.clean_text(tds[2].get_text())
                    result['changes'].append(change)
        
        return result
    
    @staticmethod
    def parse_primary_site_to_json(html: str) -> Dict[str, Any]:
        """Parse Primary Site section to JSON."""
        soup = BeautifulSoup(html, 'html.parser')
        result = {
            'title': 'Identification of Primary Site',
            'sites': [],
            'notes': []
        }
        
        # Parse topography table
        table = soup.find('table', class_='topographytable')
        if table:
            for tr in table.find_all('tr'):
                tds = tr.find_all('td')
                if len(tds) >= 2:
                    result['sites'].append({
                        'icd_o_code': TNMDataCleaner.clean_text(tds[0].get_text()),
                        'description': TNMDataCleaner.clean_text(tds[1].get_text())
                    })
        
        # Extract notes
        for note in soup.find_all('div', class_='note'):
            result['notes'].append(TNMDataCleaner.clean_text(note.get_text()))
        
        return result
    
    @staticmethod
    def parse_histopathologic_type_to_json(html: str) -> Dict[str, Any]:
        """Parse Histopathologic Type section to JSON."""
        soup = BeautifulSoup(html, 'html.parser')
        return {
            'title': 'Histopathologic Type',
            'text': TNMDataCleaner.clean_text(soup.get_text())
        }
    
    @staticmethod
    def parse_staging_rules_to_json(html: str) -> Dict[str, Any]:
        """Parse Staging Rules section to JSON."""
        soup = BeautifulSoup(html, 'html.parser')
        result = {
            'title': 'Staging Rules',
            'rules': []
        }
        
        # Parse rules table
        table = soup.find('table')
        if table:
            for tr in table.find_all('tr'):
                tds = tr.find_all('td')
                if len(tds) >= 2:
                    result['rules'].append({
                        'topic': TNMDataCleaner.clean_text(tds[0].get_text()),
                        'rule': TNMDataCleaner.clean_text(tds[1].get_text())
                    })
        
        return result


class TNMExtractor:
    """Extracts TNM staging data from AJCC website."""
    
    def __init__(self):
        self.base_url = "https://ajccstaging.org"
        self.api_base = f"{self.base_url}/api"
        
    def get_available_years(self, section_slug: str, disease_slug: str) -> List[int]:
        """
        Get list of available diagnosis years for a disease.
        
        Args:
            section_slug: AJCC section slug (e.g., "thorax")
            disease_slug: Disease slug (e.g., "lung")
            
        Returns:
            List of available years (e.g., [2024, 2025, 2026])
        """
        try:
            session = get_ajcc_session()
            url = f"{self.api_base}/content/{section_slug}/{disease_slug}?locale=en&add-headers=true"
            response = session.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            children = data.get('children', [])
            
            years = []
            for child in children:
                if isinstance(child, dict):
                    title = child.get('title', '')
                    # Check if title is a year (2024, 2025, 2026)
                    if title.isdigit() and len(title) == 4:
                        year = int(title)
                        if 2020 <= year <= 2030:  # Sanity check
                            years.append(year)
            
            # Default years if not found in children
            if not years:
                years = [2026, 2025, 2024]  # Default order
            
            return sorted(years, reverse=True)  # Latest first
            
        except Exception as e:
            print(f"[TNM_EXTRACTOR] Error getting available years: {e}")
            return [2026, 2025, 2024]  # Fallback
    
    def extract_tnm_for_disease(self, section_slug: str, disease_slug: str, year: Optional[int] = None) -> Optional[Dict]:
        """
        Extract TNM data for a specific disease.
        
        Args:
            section_slug: AJCC section slug (e.g., "thorax")
            disease_slug: Disease slug (e.g., "lung")
            year: Diagnosis year (defaults to 2026, falls back to latest available)
            
        Returns:
            Dict with all 10 sections, or None if extraction fails
        """
        try:
            # Determine year
            if year is None:
                year = 2026  # Default
            
            print(f"[TNM_EXTRACTOR] Starting extraction for {section_slug}/{disease_slug}/{year}")
            
            # Get available years and verify
            print(f"[TNM_EXTRACTOR] Getting available years...")
            available_years = self.get_available_years(section_slug, disease_slug)
            print(f"[TNM_EXTRACTOR] Available years: {available_years}")
            
            if year not in available_years:
                # Fallback to latest available
                if available_years:
                    year = available_years[0]
                    print(f"[TNM_EXTRACTOR] Year not available, using latest: {year}")
                else:
                    print(f"[TNM_EXTRACTOR] No years available for {section_slug}/{disease_slug}")
                    return None
            
            # Fetch content
            print(f"[TNM_EXTRACTOR] Getting authenticated session...")
            session = get_ajcc_session()
            url = f"{self.api_base}/content/{section_slug}/{disease_slug}/{year}?locale=en&add-headers=true"
            print(f"[TNM_EXTRACTOR] Fetching URL: {url}")
            
            # Debug: Show cookies being sent
            cookies_for_domain = [c for c in session.cookies if 'ajccstaging' in c.domain or 'facs' in c.domain]
            if cookies_for_domain:
                print(f"[TNM_EXTRACTOR] Sending {len(cookies_for_domain)} AJCC/FACS cookies")
            else:
                print(f"[TNM_EXTRACTOR] WARNING: No AJCC cookies found in session!")
            
            response = session.get(url, timeout=30)
            print(f"[TNM_EXTRACTOR] Response status: {response.status_code}")
            print(f"[TNM_EXTRACTOR] Response content-type: {response.headers.get('content-type', 'unknown')}")
            print(f"[TNM_EXTRACTOR] Response size: {len(response.content)} bytes")
            
            if response.status_code != 200:
                print(f"[TNM_EXTRACTOR] HTTP Error {response.status_code}: {response.text[:200]}")
                return None
            
            response.raise_for_status()
            
            try:
                data = response.json()
                
                # Check if data is empty
                if not data or (isinstance(data, dict) and len(data) == 0):
                    print(f"[TNM_EXTRACTOR] WARNING: API returned empty JSON object")
                    print(f"[TNM_EXTRACTOR] Raw response (first 500 chars): {response.text[:500]}")
                
                # Optional: Save raw response for debugging
                debug_mode = os.getenv('AJCC_DEBUG', '').lower() == 'true'
                if debug_mode:
                    import json
                    debug_file = f"debug_api_response_{section_slug}_{disease_slug}_{year}.json"
                    with open(debug_file, 'w') as f:
                        json.dump(data, f, indent=2)
                    print(f"[TNM_EXTRACTOR] Debug: Saved raw response to {debug_file}")
                    
            except Exception as e:
                print(f"[TNM_EXTRACTOR] Failed to parse JSON: {e}")
                print(f"[TNM_EXTRACTOR] Response text: {response.text[:500]}")
                return None
            
            html_content = data.get('content', '')
            
            # Check if we have content
            if not html_content:
                print(f"[TNM_EXTRACTOR] Main content field is empty for {section_slug}/{disease_slug}/{year}")
                print(f"[TNM_EXTRACTOR] Response data keys: {list(data.keys())[:15]}")
                
                # Check if content is in chunked_sections
                chunked_sections = data.get('chunked_sections', [])
                if chunked_sections:
                    print(f"[TNM_EXTRACTOR] Found {len(chunked_sections)} chunked sections, attempting to extract...")
                    # Debug: show structure of first chunked section
                    if chunked_sections and isinstance(chunked_sections[0], dict):
                        print(f"[TNM_EXTRACTOR] Chunked section keys: {list(chunked_sections[0].keys())}")
                    
                    # Combine all chunked section content
                    html_content = ''
                    for section in chunked_sections:
                        if isinstance(section, dict):
                            # Try different possible content keys
                            section_content = section.get('content', '') or section.get('html', '') or section.get('body', '')
                            if section_content:
                                html_content += section_content
                            elif 'title' in section:
                                print(f"[TNM_EXTRACTOR] Chunked section '{section.get('title')}' has no content")
                    
                    if html_content:
                        print(f"[TNM_EXTRACTOR] Extracted content from chunked sections, length: {len(html_content)}")
                    else:
                        print(f"[TNM_EXTRACTOR] Chunked sections found but no content extracted")
                
                # Check if we have children pages (landing page with child content pages)
                children = data.get('children', [])
                if children and not html_content:
                    print(f"[TNM_EXTRACTOR] Found {len(children)} child pages")
                    # Debug: show structure
                    if children and isinstance(children[0], dict):
                        print(f"[TNM_EXTRACTOR] Child page keys: {list(children[0].keys())}")
                        print(f"[TNM_EXTRACTOR] Child hrefs: {[c.get('href', c.get('url', 'N/A')) for c in children[:5]]}")
                    print(f"[TNM_EXTRACTOR] Child pages: {[c.get('title', 'Unknown') for c in children[:5]]}")
                    print(f"[TNM_EXTRACTOR] This is a landing page - navigating to child pages for content...")
                    
                    # Navigate to each child page and aggregate content
                    all_child_content = []
                    for child in children:
                        child_href = child.get('href', '') or child.get('url', '') or child.get('path', '')
                        child_title = child.get('title', child.get('name', 'Unknown'))
                        
                        if not child_href:
                            print(f"[TNM_EXTRACTOR] Skipping child '{child_title}' - no href/url found")
                            continue
                        
                        try:
                            # Fetch child page content
                            child_url = f"{self.api_base}/content/{child_href}?locale=en&add-headers=true"
                            print(f"[TNM_EXTRACTOR] Fetching child page: {child_title}")
                            
                            child_response = session.get(child_url, timeout=30)
                            if child_response.status_code == 200:
                                child_data = child_response.json()
                                child_content = child_data.get('content', '')
                                
                                # Also check chunked_sections in child
                                if not child_content:
                                    child_chunks = child_data.get('chunked_sections', [])
                                    if child_chunks:
                                        for chunk in child_chunks:
                                            if isinstance(chunk, dict):
                                                child_content += chunk.get('content', '') or chunk.get('html', '') or ''
                                
                                if child_content:
                                    print(f"[TNM_EXTRACTOR] ✓ Retrieved content from '{child_title}' ({len(child_content)} chars)")
                                    # Add a header to identify the section
                                    all_child_content.append(f"<!-- Section: {child_title} -->")
                                    all_child_content.append(child_content)
                                else:
                                    print(f"[TNM_EXTRACTOR] No content in '{child_title}' (keys: {list(child_data.keys())[:5]})")
                            else:
                                print(f"[TNM_EXTRACTOR] Failed to fetch '{child_title}': HTTP {child_response.status_code}")
                        
                        except Exception as e:
                            print(f"[TNM_EXTRACTOR] Error fetching child page '{child_title}': {e}")
                            continue
                    
                    # Combine all child content
                    if all_child_content:
                        html_content = '\n'.join(all_child_content)
                        print(f"[TNM_EXTRACTOR] ✓ Combined content from {len(children)} child pages ({len(html_content)} chars total)")
                    else:
                        print(f"[TNM_EXTRACTOR] No content found in any child pages")
                        return None
                
                # If still no content after checking children
                if not html_content:
                    title = data.get('title', '')
                    if title:
                        print(f"[TNM_EXTRACTOR] Page title: {title}")
                    
                    # Save raw response for debugging
                    import json
                    debug_file = f"debug_failed_extraction_{section_slug}_{disease_slug}_{year}.json"
                    try:
                        with open(debug_file, 'w') as f:
                            json.dump(data, f, indent=2, default=str)
                        print(f"[TNM_EXTRACTOR] Saved raw API response to {debug_file} for debugging")
                    except Exception as e:
                        print(f"[TNM_EXTRACTOR] Could not save debug file: {e}")
                    
                    print(f"[TNM_EXTRACTOR] No extractable content found")
                    return None
            
            print(f"[TNM_EXTRACTOR] Content retrieved, length: {len(html_content)}")
            
            # Parse all 10 sections as HTML (legacy)
            section_1_html = self.parse_section_1_quick_reference(html_content)
            section_2_html = self.parse_section_2_cancers_staged(html_content)
            section_3_html = self.parse_section_3_cancers_not_staged(html_content)
            section_4_html = self.parse_section_4_summary_changes(html_content)
            section_5_html = self.parse_section_5_primary_site(html_content)
            section_6_html = self.parse_section_6_histopathologic_type(html_content)
            section_7_html = self.parse_section_7_clinical_staging_workup(html_content)
            section_8_html = self.parse_section_8_staging_rules(html_content)
            section_9_html = self.parse_section_9_common_scenarios(html_content)
            section_10_html = self.parse_section_10_explanatory_notes(html_content)
            
            # Parse HTML sections into clean JSON
            print(f"[TNM_EXTRACTOR] Parsing HTML to structured JSON...")
            
            tnm_json = None
            if section_1_html:
                tnm_json = TNMDataCleaner.parse_quick_reference_to_json(section_1_html)
                print(f"[TNM_EXTRACTOR] ✓ Parsed TNM data: {len(tnm_json.get('t_definitions', []))} T subsites, "
                      f"{len(tnm_json.get('stage_groups', []))} stage groups")
            
            cancers_staged_json = TNMDataCleaner.parse_cancers_staged_to_json(section_2_html) if section_2_html else None
            cancers_not_staged_json = TNMDataCleaner.parse_cancers_not_staged_to_json(section_3_html) if section_3_html else None
            summary_changes_json = TNMDataCleaner.parse_summary_changes_to_json(section_4_html) if section_4_html else None
            primary_sites_json = TNMDataCleaner.parse_primary_site_to_json(section_5_html) if section_5_html else None
            histopathologic_json = TNMDataCleaner.parse_histopathologic_type_to_json(section_6_html) if section_6_html else None
            staging_rules_json = TNMDataCleaner.parse_staging_rules_to_json(section_8_html) if section_8_html else None
            
            result = {
                # JSON data (primary)
                'tnm_data_json': tnm_json,
                'cancers_staged_json': cancers_staged_json,
                'cancers_not_staged_json': cancers_not_staged_json,
                'summary_changes_json': summary_changes_json,
                'primary_sites_json': primary_sites_json,
                'histopathologic_types_json': histopathologic_json,
                'imaging_workup_json': None,  # Parsed from section 7 if available
                'staging_rules_json': staging_rules_json,
                'common_scenarios_json': None,  # Parsed from section 9 if available
                'notes_json': None,  # Can be extracted from section 10
                
                # HTML data (legacy/backup)
                'section_1_quick_reference_html': section_1_html,
                'section_2_cancers_staged_html': section_2_html,
                'section_3_cancers_not_staged_html': section_3_html,
                'section_4_summary_changes_html': section_4_html,
                'section_5_primary_site_html': section_5_html,
                'section_6_histopathologic_type_html': section_6_html,
                'section_7_clinical_staging_workup_html': section_7_html,
                'section_8_staging_rules_html': section_8_html,
                'section_9_common_scenarios_html': section_9_html,
                'section_10_explanatory_notes_html': section_10_html,
                
                # Metadata
                'raw_html_content': html_content,
                'year': year,
                'data_version': 2  # Version 2 = JSON + HTML
            }
            
            return result
            
        except Exception as e:
            print(f"[TNM_EXTRACTOR] Error extracting TNM data: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def extract_section_by_heading(self, html_content: str, heading_text: str, include_following: bool = True) -> Optional[str]:
        """
        Extract section content by heading text.
        
        Args:
            html_content: Full HTML content
            heading_text: Heading text to search for (case-insensitive partial match)
            include_following: If True, include all content until next major heading
            
        Returns:
            HTML string of the section, or None if not found
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find heading (h1, h2, h3, h4, h5, h6)
            heading = None
            for tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                headings = soup.find_all(tag_name)
                for h in headings:
                    text = h.get_text(strip=True).lower()
                    if heading_text.lower() in text:
                        heading = h
                        break
                if heading:
                    break
            
            if not heading:
                return None
            
            # Collect content until next major heading
            section_content = []
            current = heading.next_sibling
            
            while current:
                if isinstance(current, Tag):
                    # Stop at next major heading
                    if current.name in ['h1', 'h2', 'h3']:
                        # Check if it's a different major section
                        if current.name in ['h1', 'h2']:
                            break
                    
                    section_content.append(str(current))
                elif isinstance(current, NavigableString):
                    if str(current).strip():
                        section_content.append(str(current))
                
                current = current.next_sibling
            
            if section_content:
                return str(heading) + '\n' + '\n'.join(section_content)
            
            return None
            
        except Exception as e:
            print(f"[TNM_EXTRACTOR] Error extracting section by heading '{heading_text}': {e}")
            return None
    
    def parse_section_1_quick_reference(self, html_content: str) -> Optional[str]:
        """Extract Section 1: Staging Quick Reference (T, N, M, prognostic staging tables)."""
        try:
            # Look for headings related to quick reference, T stage, N stage, M stage, prognostic staging
            keywords = [
                'staging quick reference',
                'quick reference',
                't stage',
                'n stage',
                'm stage',
                'prognostic staging',
                'stage groupings'
            ]
            
            soup = BeautifulSoup(html_content, 'html.parser')
            sections = []
            
            for keyword in keywords:
                section = self.extract_section_by_heading(html_content, keyword, include_following=True)
                if section:
                    sections.append(section)
            
            # Also look for tables with T, N, M headers
            tables = soup.find_all('table')
            for table in tables:
                table_text = table.get_text().lower()
                if any(kw in table_text for kw in ['t stage', 'n stage', 'm stage', 'prognostic']):
                    sections.append(str(table))
            
            if sections:
                return '\n'.join(sections)
            
            return None
        except Exception as e:
            print(f"[TNM_EXTRACTOR] Error parsing section 1: {e}")
            return None
    
    def parse_section_2_cancers_staged(self, html_content: str) -> Optional[str]:
        """Extract Section 2: Cancers Staged Using This Staging System."""
        keywords = [
            'cancers staged using this staging system',
            'cancers staged',
            'staged using this system'
        ]
        
        for keyword in keywords:
            section = self.extract_section_by_heading(html_content, keyword, include_following=True)
            if section:
                return section
        
        return None
    
    def parse_section_3_cancers_not_staged(self, html_content: str) -> Optional[str]:
        """Extract Section 3: Cancers NOT Staged by This System."""
        keywords = [
            'cancers not staged',
            'not staged by this system',
            'cancers excluded'
        ]
        
        for keyword in keywords:
            section = self.extract_section_by_heading(html_content, keyword, include_following=True)
            if section:
                return section
        
        return None
    
    def parse_section_4_summary_changes(self, html_content: str) -> Optional[str]:
        """Extract Section 4: Summary of Changes."""
        keywords = [
            'summary of changes',
            'changes from',
            'what\'s new'
        ]
        
        for keyword in keywords:
            section = self.extract_section_by_heading(html_content, keyword, include_following=True)
            if section:
                return section
        
        return None
    
    def parse_section_5_primary_site(self, html_content: str) -> Optional[str]:
        """Extract Section 5: Identification of Primary Site."""
        keywords = [
            'identification of primary site',
            'primary site',
            'primary tumor site'
        ]
        
        for keyword in keywords:
            section = self.extract_section_by_heading(html_content, keyword, include_following=True)
            if section:
                return section
        
        return None
    
    def parse_section_6_histopathologic_type(self, html_content: str) -> Optional[str]:
        """Extract Section 6: Histopathologic Type (with Note HT)."""
        keywords = [
            'histopathologic type',
            'histologic type',
            'note ht',
            'histopathology'
        ]
        
        for keyword in keywords:
            section = self.extract_section_by_heading(html_content, keyword, include_following=True)
            if section:
                return section
        
        return None
    
    def parse_section_7_clinical_staging_workup(self, html_content: str) -> Optional[str]:
        """Extract Section 7: Clinical Staging and Workup - Imaging table only."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find "Clinical Staging and Workup" section
            section = self.extract_section_by_heading(html_content, 'clinical staging and workup', include_following=True)
            if not section:
                return None
            
            # Parse the section and extract only Imaging-related tables
            section_soup = BeautifulSoup(section, 'html.parser')
            imaging_tables = []
            
            # Look for tables with "Imaging" in headers or nearby text
            tables = section_soup.find_all('table')
            for table in tables:
                # Check table headers
                headers = table.find_all(['th', 'thead'])
                table_text = ' '.join([h.get_text().lower() for h in headers])
                
                # Check surrounding text
                prev_text = ''
                prev = table.find_previous_sibling()
                if prev:
                    prev_text = prev.get_text().lower()
                
                if 'imaging' in table_text or 'imaging' in prev_text:
                    imaging_tables.append(str(table))
            
            # Also look for "Imaging" heading and extract following table
            imaging_heading = section_soup.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'], 
                                                string=re.compile(r'imaging', re.I))
            if imaging_heading:
                next_table = imaging_heading.find_next('table')
                if next_table:
                    imaging_tables.append(str(next_table))
            
            if imaging_tables:
                return '\n'.join(imaging_tables)
            
            return None
        except Exception as e:
            print(f"[TNM_EXTRACTOR] Error parsing section 7: {e}")
            return None
    
    def parse_section_8_staging_rules(self, html_content: str) -> Optional[str]:
        """Extract Section 8: Staging Rules for [Disease]."""
        keywords = [
            'staging rules',
            'rules for staging',
            'staging criteria'
        ]
        
        for keyword in keywords:
            section = self.extract_section_by_heading(html_content, keyword, include_following=True)
            if section:
                return section
        
        return None
    
    def parse_section_9_common_scenarios(self, html_content: str) -> Optional[str]:
        """Extract Section 9: Common Staging Scenarios."""
        keywords = [
            'common staging scenarios',
            'common scenarios',
            'staging examples',
            'example scenarios'
        ]
        
        for keyword in keywords:
            section = self.extract_section_by_heading(html_content, keyword, include_following=True)
            if section:
                return section
        
        return None
    
    def parse_section_10_explanatory_notes(self, html_content: str) -> Optional[str]:
        """Extract Section 10: Explanatory Notes - full page with all figures and tables."""
        keywords = [
            'explanatory notes',
            'explanatory note',
            'notes and figures',
            'additional notes'
        ]
        
        for keyword in keywords:
            section = self.extract_section_by_heading(html_content, keyword, include_following=True)
            if section:
                # Include all figures and tables
                soup = BeautifulSoup(section, 'html.parser')
                
                # Find all images/figures
                images = soup.find_all('img')
                figures = soup.find_all('figure')
                
                # Find all tables
                tables = soup.find_all('table')
                
                # Return full section with all content
                return section
        
        # If no specific section found, return a portion of the content
        # This is a fallback - ideally we want the specific section
        return None
    
    def save_to_database(self, staging_data_dict: Dict, disease_site: AJCCDiseaseSite, 
                        year: int, user_id: int) -> Optional[AJCCStagingData]:
        """
        Save extracted staging data to database.
        
        Args:
            staging_data_dict: Dict with JSON and HTML content
            disease_site: AJCCDiseaseSite object
            year: Diagnosis year
            user_id: User ID who extracted the data
            
        Returns:
            AJCCStagingData object or None if save fails
        """
        try:
            # Get or create diagnosis year
            diagnosis_year = AJCCDiagnosisYear.query.filter_by(year=year).first()
            if not diagnosis_year:
                diagnosis_year = AJCCDiagnosisYear(year=year, is_default=(year == 2026))
                db.session.add(diagnosis_year)
                db.session.flush()
            
            # Check if staging data already exists
            staging_data = AJCCStagingData.query.filter_by(
                disease_site_id=disease_site.id,
                diagnosis_year_id=diagnosis_year.id
            ).first()
            
            # Helper to serialize JSON data
            def serialize_json(data):
                if data is None:
                    return None
                return json.dumps(data, ensure_ascii=False)
            
            if staging_data:
                # Update existing record
                print(f"[TNM_EXTRACTOR] Updating existing record for {disease_site.disease_name} ({year})")
                
                # Update JSON fields
                staging_data.tnm_data_json = serialize_json(staging_data_dict.get('tnm_data_json'))
                staging_data.cancers_staged_json = serialize_json(staging_data_dict.get('cancers_staged_json'))
                staging_data.cancers_not_staged_json = serialize_json(staging_data_dict.get('cancers_not_staged_json'))
                staging_data.summary_changes_json = serialize_json(staging_data_dict.get('summary_changes_json'))
                staging_data.primary_sites_json = serialize_json(staging_data_dict.get('primary_sites_json'))
                staging_data.histopathologic_types_json = serialize_json(staging_data_dict.get('histopathologic_types_json'))
                staging_data.imaging_workup_json = serialize_json(staging_data_dict.get('imaging_workup_json'))
                staging_data.staging_rules_json = serialize_json(staging_data_dict.get('staging_rules_json'))
                staging_data.common_scenarios_json = serialize_json(staging_data_dict.get('common_scenarios_json'))
                staging_data.notes_json = serialize_json(staging_data_dict.get('notes_json'))
                
                # Update HTML fields (legacy)
                for key, value in staging_data_dict.items():
                    if key.startswith('section_') and key.endswith('_html'):
                        setattr(staging_data, key, value)
                
                staging_data.raw_html_content = staging_data_dict.get('raw_html_content')
                staging_data.data_version = staging_data_dict.get('data_version', 2)
                staging_data.last_updated_at = datetime.utcnow()
            else:
                # Create new record
                print(f"[TNM_EXTRACTOR] Creating new record for {disease_site.disease_name} ({year})")
                
                staging_data = AJCCStagingData(
                    disease_site_id=disease_site.id,
                    diagnosis_year_id=diagnosis_year.id,
                    
                    # JSON fields (primary data)
                    tnm_data_json=serialize_json(staging_data_dict.get('tnm_data_json')),
                    cancers_staged_json=serialize_json(staging_data_dict.get('cancers_staged_json')),
                    cancers_not_staged_json=serialize_json(staging_data_dict.get('cancers_not_staged_json')),
                    summary_changes_json=serialize_json(staging_data_dict.get('summary_changes_json')),
                    primary_sites_json=serialize_json(staging_data_dict.get('primary_sites_json')),
                    histopathologic_types_json=serialize_json(staging_data_dict.get('histopathologic_types_json')),
                    imaging_workup_json=serialize_json(staging_data_dict.get('imaging_workup_json')),
                    staging_rules_json=serialize_json(staging_data_dict.get('staging_rules_json')),
                    common_scenarios_json=serialize_json(staging_data_dict.get('common_scenarios_json')),
                    notes_json=serialize_json(staging_data_dict.get('notes_json')),
                    
                    # HTML fields (legacy/backup)
                    section_1_quick_reference_html=staging_data_dict.get('section_1_quick_reference_html'),
                    section_2_cancers_staged_html=staging_data_dict.get('section_2_cancers_staged_html'),
                    section_3_cancers_not_staged_html=staging_data_dict.get('section_3_cancers_not_staged_html'),
                    section_4_summary_changes_html=staging_data_dict.get('section_4_summary_changes_html'),
                    section_5_primary_site_html=staging_data_dict.get('section_5_primary_site_html'),
                    section_6_histopathologic_type_html=staging_data_dict.get('section_6_histopathologic_type_html'),
                    section_7_clinical_staging_workup_html=staging_data_dict.get('section_7_clinical_staging_workup_html'),
                    section_8_staging_rules_html=staging_data_dict.get('section_8_staging_rules_html'),
                    section_9_common_scenarios_html=staging_data_dict.get('section_9_common_scenarios_html'),
                    section_10_explanatory_notes_html=staging_data_dict.get('section_10_explanatory_notes_html'),
                    
                    # Metadata
                    raw_html_content=staging_data_dict.get('raw_html_content'),
                    data_version=staging_data_dict.get('data_version', 2),
                    extracted_by_user_id=user_id
                )
                db.session.add(staging_data)
            
            db.session.commit()
            print(f"[TNM_EXTRACTOR] ✓ Saved staging data (version {staging_data.data_version})")
            return staging_data
            
        except Exception as e:
            db.session.rollback()
            print(f"[TNM_EXTRACTOR] Error saving to database: {e}")
            import traceback
            traceback.print_exc()
            return None
