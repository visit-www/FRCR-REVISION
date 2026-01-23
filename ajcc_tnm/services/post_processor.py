"""
AJCC TNM Post-Processor Service

Handles post-extraction processing:
- Parses HTML to JSON (if not already done)
- Downloads images from AJCC CDN to Cloudinary
- Normalizes data for database storage
"""

import os
import re
import json
import hashlib
from typing import Optional, Dict, List, Any
from datetime import datetime
from bs4 import BeautifulSoup

try:
    import cloudinary
    import cloudinary.uploader
    CLOUDINARY_AVAILABLE = True
except ImportError:
    CLOUDINARY_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class PostProcessor:
    """
    Post-processes extracted AJCC data.
    
    Features:
    - Re-parse HTML sections to JSON if needed
    - Download and upload images to Cloudinary
    - Clean and normalize data
    """
    
    def __init__(self, cloudinary_folder: str = 'ajcc_tnm/images'):
        """
        Initialize the post-processor.
        
        Args:
            cloudinary_folder: Folder path in Cloudinary for uploaded images
        """
        self.cloudinary_folder = cloudinary_folder
        self.image_cache = {}  # Cache for already processed images
        
    def process_staging_data(self, staging_data) -> Dict[str, Any]:
        """
        Process a staging data record.
        
        Args:
            staging_data: AJCCStagingData model instance
            
        Returns:
            Dict with processing results
        """
        results = {
            'success': True,
            'images_processed': 0,
            'errors': []
        }
        
        # Process images in explanatory notes
        if staging_data.section_10_explanatory_notes_html:
            try:
                updated_html, image_count = self.process_images_in_html(
                    staging_data.section_10_explanatory_notes_html,
                    staging_data.id
                )
                staging_data.section_10_explanatory_notes_html = updated_html
                results['images_processed'] += image_count
            except Exception as e:
                results['errors'].append(f"Error processing section 10 images: {str(e)}")
        
        # Process other sections with potential images
        for section_num in [7, 8, 9]:  # Clinical staging, rules, scenarios
            html = staging_data.get_section_html(section_num)
            if html:
                try:
                    updated_html, image_count = self.process_images_in_html(
                        html, staging_data.id
                    )
                    staging_data.set_section_html(section_num, updated_html)
                    results['images_processed'] += image_count
                except Exception as e:
                    results['errors'].append(f"Error processing section {section_num} images: {str(e)}")
        
        if results['errors']:
            results['success'] = False
            
        return results
    
    def process_images_in_html(self, html: str, staging_data_id: int) -> tuple:
        """
        Find and process images in HTML content.
        
        Args:
            html: HTML content
            staging_data_id: ID of the staging data record
            
        Returns:
            Tuple of (updated_html, image_count)
        """
        if not html:
            return html, 0
            
        soup = BeautifulSoup(html, 'html.parser')
        images = soup.find_all('img')
        image_count = 0
        
        for img in images:
            src = img.get('src', '')
            if not src:
                continue
                
            # Skip already processed images (Cloudinary URLs)
            if 'cloudinary' in src or 'res.cloudinary.com' in src:
                continue
                
            # Skip data URLs
            if src.startswith('data:'):
                continue
            
            # Process AJCC CDN images
            if 'ajccstaging.org' in src or src.startswith('/'):
                try:
                    new_url = self.upload_image_to_cloudinary(
                        src, 
                        staging_data_id
                    )
                    if new_url:
                        img['src'] = new_url
                        img['data-original-src'] = src  # Keep original for reference
                        image_count += 1
                except Exception as e:
                    print(f"[POST_PROCESSOR] Error uploading image {src}: {e}")
        
        return str(soup), image_count
    
    def upload_image_to_cloudinary(self, image_url: str, staging_data_id: int) -> Optional[str]:
        """
        Download an image and upload it to Cloudinary.
        
        Args:
            image_url: Source URL of the image
            staging_data_id: ID for organizing in Cloudinary
            
        Returns:
            Cloudinary URL or None if failed
        """
        if not CLOUDINARY_AVAILABLE:
            print("[POST_PROCESSOR] Cloudinary not available")
            return None
            
        if not REQUESTS_AVAILABLE:
            print("[POST_PROCESSOR] Requests not available")
            return None
        
        # Check cache
        url_hash = hashlib.md5(image_url.encode()).hexdigest()
        if url_hash in self.image_cache:
            return self.image_cache[url_hash]
        
        try:
            # Make URL absolute if needed
            if image_url.startswith('/'):
                image_url = f"https://ajccstaging.org{image_url}"
            
            # Download image
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            # Generate public ID
            public_id = f"{self.cloudinary_folder}/staging_{staging_data_id}/{url_hash}"
            
            # Upload to Cloudinary
            result = cloudinary.uploader.upload(
                response.content,
                public_id=public_id,
                resource_type='image',
                overwrite=True
            )
            
            cloudinary_url = result.get('secure_url')
            
            # Cache the result
            self.image_cache[url_hash] = cloudinary_url
            
            print(f"[POST_PROCESSOR] Uploaded image: {cloudinary_url}")
            return cloudinary_url
            
        except Exception as e:
            print(f"[POST_PROCESSOR] Error uploading {image_url}: {e}")
            return None
    
    def extract_figures_from_html(self, html: str) -> List[Dict[str, Any]]:
        """
        Extract figure information from HTML.
        
        Args:
            html: HTML content
            
        Returns:
            List of figure dictionaries
        """
        figures = []
        if not html:
            return figures
            
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find figure elements
        for fig in soup.find_all('figure'):
            img = fig.find('img')
            caption = fig.find('figcaption')
            
            if img:
                figures.append({
                    'src': img.get('src', ''),
                    'alt': img.get('alt', ''),
                    'caption': caption.get_text(strip=True) if caption else '',
                    'cloudinary_url': img.get('data-cloudinary-url', '')
                })
        
        # Also find standalone images with captions
        for img in soup.find_all('img'):
            if img.find_parent('figure'):
                continue  # Already processed
                
            # Look for caption in nearby text
            caption = ''
            next_elem = img.find_next_sibling()
            if next_elem and next_elem.name in ['p', 'div', 'span']:
                text = next_elem.get_text(strip=True)
                if text.lower().startswith('figure') or text.lower().startswith('fig'):
                    caption = text
            
            figures.append({
                'src': img.get('src', ''),
                'alt': img.get('alt', ''),
                'caption': caption,
                'cloudinary_url': img.get('data-cloudinary-url', '')
            })
        
        return figures
    
    def clean_html(self, html: str) -> str:
        """
        Clean HTML content by removing unnecessary attributes and elements.
        
        Args:
            html: Raw HTML content
            
        Returns:
            Cleaned HTML
        """
        if not html:
            return html
            
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script and style tags
        for tag in soup.find_all(['script', 'style']):
            tag.decompose()
        
        # Remove empty elements
        for tag in soup.find_all():
            if not tag.get_text(strip=True) and not tag.find_all(['img', 'table', 'figure']):
                tag.decompose()
        
        # Remove unnecessary attributes
        attrs_to_keep = ['src', 'alt', 'href', 'class', 'id', 'colspan', 'rowspan']
        for tag in soup.find_all():
            attrs = dict(tag.attrs)
            for attr in attrs:
                if attr not in attrs_to_keep:
                    del tag[attr]
        
        return str(soup)
    
    def reparse_staging_data(self, staging_data) -> bool:
        """
        Re-parse HTML sections to JSON for a staging data record.
        
        Args:
            staging_data: AJCCStagingData model instance
            
        Returns:
            True if successful
        """
        from .extractor import TNMDataCleaner
        
        try:
            # Re-parse Section 1 (Quick Reference) to TNM JSON
            section_1 = staging_data.section_1_quick_reference_html
            if section_1 and not staging_data.tnm_data_json:
                tnm_json = TNMDataCleaner.parse_quick_reference_to_json(section_1)
                staging_data.set_tnm_data(tnm_json)
            
            # Re-parse other sections
            section_parsers = {
                2: ('cancers_staged', TNMDataCleaner.parse_cancers_staged_to_json),
                3: ('cancers_not_staged', TNMDataCleaner.parse_cancers_not_staged_to_json),
                4: ('summary_changes', TNMDataCleaner.parse_summary_changes_to_json),
                5: ('primary_sites', TNMDataCleaner.parse_primary_site_to_json),
                6: ('histopathologic_types', TNMDataCleaner.parse_histopathologic_type_to_json),
                8: ('staging_rules', TNMDataCleaner.parse_staging_rules_to_json),
            }
            
            for section_num, (json_field, parser) in section_parsers.items():
                html = staging_data.get_section_html(section_num)
                current_json = staging_data.get_json_section(json_field)
                
                if html and not current_json:
                    parsed = parser(html)
                    staging_data.set_json_section(json_field, parsed)
            
            staging_data.data_version = 2
            return True
            
        except Exception as e:
            print(f"[POST_PROCESSOR] Error re-parsing staging data: {e}")
            return False


def process_all_staging_data(db_session) -> Dict[str, Any]:
    """
    Process all staging data records in the database.
    
    Args:
        db_session: SQLAlchemy database session
        
    Returns:
        Dict with processing statistics
    """
    from models import AJCCStagingData
    
    processor = PostProcessor()
    stats = {
        'total': 0,
        'processed': 0,
        'errors': 0,
        'images_uploaded': 0
    }
    
    staging_records = AJCCStagingData.query.all()
    stats['total'] = len(staging_records)
    
    for staging in staging_records:
        try:
            # Re-parse if needed
            if staging.data_version < 2:
                processor.reparse_staging_data(staging)
            
            # Process images
            result = processor.process_staging_data(staging)
            stats['images_uploaded'] += result['images_processed']
            
            if result['success']:
                stats['processed'] += 1
            else:
                stats['errors'] += 1
                
            db_session.commit()
            
        except Exception as e:
            print(f"[POST_PROCESSOR] Error processing staging {staging.id}: {e}")
            stats['errors'] += 1
            db_session.rollback()
    
    return stats
