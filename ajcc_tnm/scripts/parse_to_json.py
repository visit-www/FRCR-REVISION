#!/usr/bin/env python3
"""
Parse AJCC HTML data into clean JSON format.
Removes junk metadata, unnecessary classes/IDs, and extracts structured TNM data.
"""

import os
import sys
import re
import json
from bs4 import BeautifulSoup, NavigableString

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import AJCCStagingData


def clean_text(text):
    """Remove extra whitespace and normalize text"""
    if not text:
        return ""
    # Remove the DITA path junk like [/concept/Tdefinition/...] and {""}) 
    text = re.sub(r'\[/concept/[^\]]+', '', text)
    text = re.sub(r'\{["\s]*\}\s*\)', '', text)
    text = re.sub(r'\(validvalue\]', '', text)
    text = re.sub(r'\[validvalue\]', '', text)
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_tnm_value(cell_html):
    """Extract the actual TNM value (TX, T1, N0, M1, etc.) from messy cell HTML"""
    # First, get the raw text from HTML
    soup = BeautifulSoup(cell_html, 'html.parser')
    text = soup.get_text()
    
    # Look for TNM pattern in the messy text - it's usually between ") " and " ("
    # Pattern like: {""}) TX  (validvalue]
    # The actual value is: TX, Tis, T1, T1a, T2, N0, N1, M0, M1, etc.
    
    # Try to find the TNM code pattern
    tnm_patterns = [
        r'\)\s*(Tis)\s*\(',                 # Tis specifically (carcinoma in situ)
        r'\)\s*(TX)\s*\(',                  # TX specifically
        r'\)\s*(T[0-4][ab]?)\s*\(',         # T categories: T1, T1a, T1b, T2, T3, T4, T4a, T4b
        r'\)\s*(N[X0-3][abc]?)\s*\(',       # N categories: NX, N0, N1, N2, N2a, N2b, N2c, N3, N3a, N3b
        r'\)\s*(M[01X])\s*\(',              # M categories: M0, M1, MX
        r'\b(Tis)\b',                        # Fallback for Tis
        r'\b(TX|T[0-4][ab]?)\b',             # Fallback for T
        r'\b(NX|N[0-3][abc]?)\b',            # Fallback for N
        r'\b(MX|M[01])\b',                   # Fallback for M
    ]
    
    for pattern in tnm_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # If no pattern found, try cleaning and returning
    cleaned = clean_text(text)
    return cleaned if len(cleaned) < 10 else ""


def parse_tnm_table(table_soup, table_type='T'):
    """Parse a T, N, or M definition table into structured data"""
    rows = []
    for tr in table_soup.find_all('tr', class_='TNMrow'):
        category_td = tr.find('td', class_='AJCCcategory')
        criteria_td = tr.find('td', class_='AJCCcriteria')
        
        if category_td and criteria_td:
            # Extract clean category value
            category = extract_tnm_value(str(category_td))
            # Clean criteria text, preserving emphasis
            criteria_html = str(criteria_td)
            criteria_soup = BeautifulSoup(criteria_html, 'html.parser')
            criteria = clean_text(criteria_soup.get_text())
            
            rows.append({
                'category': category,
                'criteria': criteria
            })
    
    return rows


def parse_stage_group_table(table_soup):
    """Parse the stage group table into structured data"""
    rows = []
    for tr in table_soup.find_all('tr', class_='stagerow'):
        t_val = tr.find('td', class_='Tvalue')
        n_val = tr.find('td', class_='Nvalue')
        m_val = tr.find('td', class_='Mvalue')
        stage = tr.find('td', class_='stagegroup')
        
        if all([t_val, n_val, m_val, stage]):
            rows.append({
                'T': clean_text(t_val.get_text()),
                'N': clean_text(n_val.get_text()),
                'M': clean_text(m_val.get_text()),
                'stage': clean_text(stage.get_text())
            })
    
    return rows


def parse_quick_reference_html(html):
    """Parse the Quick Reference section HTML into structured JSON"""
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
        result['title'] = clean_text(title_elem.get_text())
    
    # Parse T definitions (may have multiple subsites like Glottis, Subglottis, Supraglottis)
    t_articles = soup.find_all('article', class_='Tdefinition')
    for article in t_articles:
        heading = article.find(['h2', 'h3'])
        subsite_name = clean_text(heading.get_text()) if heading else 'Unknown'
        # Clean up the heading
        subsite_name = re.sub(r'^\*?Definition of Primary Tumor \(T\)\s*(\(Note T\)\s*)?', '', subsite_name)
        
        table = article.find('table', class_='Ttable')
        if table:
            t_data = parse_tnm_table(table, 'T')
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
            n_data = parse_tnm_table(table, 'N')
            if 'pN' in heading_text or 'pathological' in heading_text.lower():
                result['n_definitions']['pathological'] = n_data
            else:
                result['n_definitions']['clinical'] = n_data
        
        # Extract notes
        for note in article.find_all('div', class_='note'):
            note_text = clean_text(note.get_text())
            if note_text and note_text not in result['notes']:
                result['notes'].append(note_text)
    
    # Parse M definitions
    m_articles = soup.find_all('article', class_='Mdefinition')
    for article in m_articles:
        table = article.find('table', class_='Mtable')
        if table:
            result['m_definitions'] = parse_tnm_table(table, 'M')
    
    # Parse stage group table
    stage_section = soup.find('article', class_='stagesection')
    if stage_section:
        table = stage_section.find('table', class_='stagetable')
        if table:
            result['stage_groups'] = parse_stage_group_table(table)
    
    return result


def clean_html_for_display(html):
    """Clean HTML for display - remove junk but keep structure"""
    if not html:
        return html
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Remove all the junk span elements with DITA paths
    for span in soup.find_all('span', style=True):
        if 'background-color: yellow' in span.get('style', ''):
            # This is a junk span - extract just the TNM value
            text = span.get_text()
            # Clean the text
            clean = clean_text(text)
            span.replace_with(clean)
    
    # Remove unnecessary IDs (keep class for styling)
    for tag in soup.find_all(True):
        if tag.get('id') and ('ariaid' in tag.get('id', '') or 
                              re.match(r'[A-Z]definition-\d+', tag.get('id', '')) or
                              re.match(r'stageprognostic-\d+', tag.get('id', '')) or
                              re.match(r'stagesection-\d+', tag.get('id', '')) or
                              re.match(r'concept-\d+', tag.get('id', ''))):
            del tag['id']
        
        # Simplify classes
        if tag.get('class'):
            # Keep only essential classes
            essential = ['Ttable', 'Ntable', 'Mtable', 'stagetable', 
                        'TNMrow', 'stagerow', 'AJCCcategory', 'AJCCcriteria',
                        'Tvalue', 'Nvalue', 'Mvalue', 'stagegroup',
                        'note', 'table', 'tbody', 'thead']
            new_classes = [c for c in tag['class'] if c in essential]
            if new_classes:
                tag['class'] = new_classes
            else:
                del tag['class']
        
        # Remove aria labels
        if tag.get('aria-labelledby'):
            del tag['aria-labelledby']
    
    # Clean up whitespace
    html_str = str(soup)
    html_str = re.sub(r'\n\s*\n', '\n', html_str)
    html_str = re.sub(r'>\s+<', '><', html_str)
    
    return html_str


def convert_staging_to_json(staging_record):
    """Convert a staging record to clean JSON format"""
    result = {
        'disease_name': staging_record.disease_site.disease_name if staging_record.disease_site else None,
        'disease_slug': staging_record.disease_site.slug if staging_record.disease_site else None,
        'diagnosis_year': staging_record.diagnosis_year.year if staging_record.diagnosis_year else None,
        'extracted_at': staging_record.extracted_at.isoformat() if staging_record.extracted_at else None,
        'sections': {}
    }
    
    # Parse Quick Reference (section 1) into structured data
    quick_ref_html = staging_record.get_section_html(1)
    if quick_ref_html:
        result['sections']['quick_reference'] = {
            'raw_html_cleaned': clean_html_for_display(quick_ref_html),
            'structured_data': parse_quick_reference_html(quick_ref_html)
        }
    
    # Other sections - just clean the HTML
    section_map = {
        2: 'cancers_staged',
        3: 'cancers_not_staged', 
        4: 'summary_changes',
        5: 'primary_site',
        6: 'histopathologic_type',
        7: 'clinical_staging_workup',
        8: 'staging_rules',
        9: 'common_scenarios',
        10: 'explanatory_notes'
    }
    
    for num, name in section_map.items():
        html = staging_record.get_section_html(num)
        if html:
            result['sections'][name] = {
                'raw_html_cleaned': clean_html_for_display(html),
                'text_content': clean_text(BeautifulSoup(html, 'html.parser').get_text())
            }
    
    return result


def main():
    """Main function to parse and export AJCC data"""
    with app.app_context():
        staging = AJCCStagingData.query.first()
        if not staging:
            print("No staging data found")
            return
        
        # Convert to clean JSON
        clean_data = convert_staging_to_json(staging)
        
        # Export structured data only (without HTML)
        structured_only = {
            'disease_name': clean_data['disease_name'],
            'diagnosis_year': clean_data['diagnosis_year'],
            'tnm_staging': clean_data['sections'].get('quick_reference', {}).get('structured_data', {})
        }
        
        # Save full cleaned data
        with open('ajcc_cleaned_full.json', 'w', encoding='utf-8') as f:
            json.dump(clean_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Full cleaned data saved to: ajcc_cleaned_full.json")
        
        # Save structured TNM data only
        with open('ajcc_tnm_structured.json', 'w', encoding='utf-8') as f:
            json.dump(structured_only, f, indent=2, ensure_ascii=False)
        print(f"✅ Structured TNM data saved to: ajcc_tnm_structured.json")
        
        # Print sample of structured data
        print("\n" + "="*60)
        print("SAMPLE: Structured TNM Data")
        print("="*60)
        tnm = structured_only['tnm_staging']
        
        if tnm.get('t_definitions'):
            print(f"\n📋 T Definitions ({len(tnm['t_definitions'])} subsites):")
            for subsite in tnm['t_definitions'][:1]:  # Show first subsite
                print(f"   Subsite: {subsite['subsite']}")
                for cat in subsite['categories'][:3]:  # Show first 3 categories
                    print(f"   - {cat['category']}: {cat['criteria'][:60]}...")
        
        if tnm.get('n_definitions', {}).get('clinical'):
            print(f"\n📋 N Definitions (Clinical):")
            for cat in tnm['n_definitions']['clinical'][:3]:
                print(f"   - {cat['category']}: {cat['criteria'][:60]}...")
        
        if tnm.get('m_definitions'):
            print(f"\n📋 M Definitions:")
            for cat in tnm['m_definitions']:
                print(f"   - {cat['category']}: {cat['criteria']}")
        
        if tnm.get('stage_groups'):
            print(f"\n📋 Stage Groups ({len(tnm['stage_groups'])} combinations):")
            for sg in tnm['stage_groups'][:3]:
                print(f"   - T={sg['T']}, N={sg['N']}, M={sg['M']} → Stage {sg['stage']}")


if __name__ == '__main__':
    main()
