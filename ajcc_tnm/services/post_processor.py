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

try:
    from browser_automation_service import BrowserAutomationService
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class PostProcessor:
    """
    Post-processes extracted AJCC data.
    
    Features:
    - Re-parse HTML sections to JSON if needed
    - Download and upload images to Cloudinary
    - Clean and normalize data
    """
    
    def __init__(self, cloudinary_folder: str = 'Frcr-revision-media/AJCC_figures', authenticated_session: Optional[requests.Session] = None, browser_service: Optional[Any] = None):
        """
        Initialize the post-processor.
        
        Args:
            cloudinary_folder: Folder path in Cloudinary for uploaded images
            authenticated_session: Optional authenticated requests.Session for downloading AJCC images
            browser_service: Optional BrowserAutomationService instance for Playwright navigation
        """
        self.cloudinary_folder = cloudinary_folder
        self.image_cache = {}  # Cache for already processed images
        self.session = authenticated_session if authenticated_session else requests.Session()
        self.browser_service = browser_service
        
    def process_staging_data(self, staging_data, use_playwright: bool = True) -> Dict[str, Any]:
        """
        Process a staging data record.
        
        Args:
            staging_data: AJCCStagingData model instance
            use_playwright: If True, use Playwright to extract fresh URLs from AJCC pages
            
        Returns:
            Dict with processing results
        """
        results = {
            'success': True,
            'images_processed': 0,
            'errors': []
        }
        
        # Use Playwright-based processing if available and requested
        if use_playwright and self.browser_service and PLAYWRIGHT_AVAILABLE:
            # Process images in explanatory notes
            if staging_data.section_10_explanatory_notes_html:
                try:
                    updated_html, image_count = self.process_images_with_fresh_urls(
                        staging_data.section_10_explanatory_notes_html,
                        staging_data.id,
                        staging_data,
                        self.browser_service
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
                        updated_html, image_count = self.process_images_with_fresh_urls(
                            html, staging_data.id, staging_data, self.browser_service
                        )
                        staging_data.set_section_html(section_num, updated_html)
                        results['images_processed'] += image_count
                    except Exception as e:
                        results['errors'].append(f"Error processing section {section_num} images: {str(e)}")
        else:
            # Fallback to original method
            # Process images in explanatory notes
            if staging_data.section_10_explanatory_notes_html:
                try:
                    updated_html, image_count = self.process_images_in_html(
                        staging_data.section_10_explanatory_notes_html,
                        staging_data.id,
                        self.session
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
                            html, staging_data.id, self.session
                        )
                        staging_data.set_section_html(section_num, updated_html)
                        results['images_processed'] += image_count
                    except Exception as e:
                        results['errors'].append(f"Error processing section {section_num} images: {str(e)}")
        
        if results['errors']:
            results['success'] = False
            
        return results
    
    def process_images_in_html(self, html: str, staging_data_id: int, session: Optional[requests.Session] = None) -> tuple:
        """
        Find and process images in HTML content.
        
        Args:
            html: HTML content
            staging_data_id: ID of the staging data record
            session: Optional authenticated requests.Session for downloading (uses self.session if not provided)
            
        Returns:
            Tuple of (updated_html, image_count)
        """
        if not html:
            return html, 0
        
        # Use provided session or fall back to instance session
        download_session = session if session else self.session
            
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
            
            # Process AJCC CDN images (including ajcc.deploy.heretto.com with JWT tokens)
            if ('ajccstaging.org' in src or 
                'ajcc.deploy.heretto.com' in src or 
                src.startswith('/')):
                try:
                    new_url = self.upload_image_to_cloudinary(
                        src, 
                        staging_data_id,
                        download_session
                    )
                    if new_url:
                        img['src'] = new_url
                        img['data-original-src'] = src  # Keep original for reference
                        image_count += 1
                except Exception as e:
                    print(f"[POST_PROCESSOR] Error uploading image {src}: {e}")
        
        return str(soup), image_count
    
    def extract_fresh_image_urls_from_page(self, staging_data, browser_service: Any) -> Dict[str, str]:
        """
        Navigate to AJCC page and extract fresh image URLs.
        
        Args:
            staging_data: AJCCStagingData model instance
            browser_service: BrowserAutomationService instance
            
        Returns:
            Dict mapping old UUIDs to new fresh image URLs
        """
        url_mapping = {}
        
        if not PLAYWRIGHT_AVAILABLE or not browser_service:
            return url_mapping
        
        try:
            # Construct AJCC page URL
            if not staging_data.disease_site or not staging_data.disease_site.ajcc_url_path:
                print(f"[POST_PROCESSOR] No ajcc_url_path for staging {staging_data.id}")
                return url_mapping
            
            ajcc_url_path = staging_data.disease_site.ajcc_url_path
            year = staging_data.diagnosis_year.year if staging_data.diagnosis_year else None
            
            # Construct URL: https://ajccstaging.org/en/{path}/{year}
            if year:
                page_url = f"https://ajccstaging.org/en/{ajcc_url_path}/{year}"
            else:
                page_url = f"https://ajccstaging.org/en/{ajcc_url_path}"
            
            print(f"[POST_PROCESSOR] Navigating to {page_url} to extract fresh image URLs...")
            
            # Collect network requests to find image URLs
            image_urls_from_network = []
            seen_urls = set()  # Avoid duplicates
            
            def handle_response(response):
                """Capture image URLs from network responses"""
                try:
                    url = response.url
                    # Check if it's an image URL from heretto.com
                    if 'ajcc.deploy.heretto.com' in url and '/object/' in url:
                        # Check content type or URL pattern
                        content_type = response.headers.get('content-type', '')
                        if url not in seen_urls and ('image' in content_type.lower() or 'jwt=' in url):
                            image_urls_from_network.append(url)
                            seen_urls.add(url)
                except Exception as e:
                    pass
            
            # Set up response listener BEFORE navigation
            browser_service.page.on("response", handle_response)
            
            # Also listen to requests in case images are requested
            def handle_request(request):
                """Capture image URLs from network requests"""
                try:
                    url = request.url
                    if 'ajcc.deploy.heretto.com' in url and '/object/' in url and url not in seen_urls:
                        image_urls_from_network.append(url)
                        seen_urls.add(url)
                except:
                    pass
            
            browser_service.page.on("request", handle_request)
            
            # Navigate to page
            browser_service.navigate(page_url, wait_until="networkidle", timeout=30000)
            
            # Wait for images to load - wait for img elements to appear
            try:
                browser_service.page.wait_for_selector('img', timeout=10000)
            except:
                pass  # Continue even if no images found immediately
            
            # Wait additional time for lazy-loaded images
            browser_service.page.wait_for_timeout(5000)  # Wait 5 seconds for images
            
            # Scroll page to trigger lazy loading
            browser_service.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            browser_service.page.wait_for_timeout(2000)
            browser_service.page.evaluate("window.scrollTo(0, 0)")
            browser_service.page.wait_for_timeout(2000)
            
            # Get page HTML
            page_html = browser_service.page.content()
            page_soup = BeautifulSoup(page_html, 'html.parser')
            
            # Process network-captured URLs first (most reliable)
            for network_url in image_urls_from_network:
                uuid_match = re.search(r'/object/([a-f0-9\-]+)', network_url)
                if uuid_match:
                    object_uuid = uuid_match.group(1)
                    url_mapping[object_uuid] = network_url
                    print(f"[POST_PROCESSOR] Found fresh URL from network for UUID {object_uuid}: {network_url[:80]}...")
            
            print(f"[POST_PROCESSOR] Captured {len(image_urls_from_network)} image URLs from network requests")
            
            # Also check for images in style attributes and data attributes
            # Extract all image URLs from the page
            images = page_soup.find_all('img')
            for img in images:
                # Check src attribute
                src = img.get('src', '')
                if not src:
                    # Check data-src (lazy loading)
                    src = img.get('data-src', '')
                if not src:
                    # Check srcset
                    srcset = img.get('srcset', '')
                    if srcset:
                        # Extract first URL from srcset
                        src = srcset.split(',')[0].strip().split(' ')[0]
                
                if src:
                    # Only process heretto.com URLs
                    if 'ajcc.deploy.heretto.com' in src:
                        # Extract UUID from URL
                        uuid_match = re.search(r'/object/([a-f0-9\-]+)', src)
                        if uuid_match:
                            object_uuid = uuid_match.group(1)
                            url_mapping[object_uuid] = src
                            print(f"[POST_PROCESSOR] Found fresh URL for UUID {object_uuid}: {src[:80]}...")
            
            # Also check for background images in style attributes
            elements_with_bg = page_soup.find_all(style=re.compile(r'background.*url'))
            for elem in elements_with_bg:
                style = elem.get('style', '')
                url_match = re.search(r'url\(["\']?([^"\']+)["\']?\)', style)
                if url_match:
                    bg_url = url_match.group(1)
                    if 'ajcc.deploy.heretto.com' in bg_url:
                        uuid_match = re.search(r'/object/([a-f0-9\-]+)', bg_url)
                        if uuid_match:
                            object_uuid = uuid_match.group(1)
                            url_mapping[object_uuid] = bg_url
                            print(f"[POST_PROCESSOR] Found fresh background URL for UUID {object_uuid}")
            
            print(f"[POST_PROCESSOR] Extracted {len(url_mapping)} fresh image URLs from page (network: {len(image_urls_from_network)}, HTML: {len(url_mapping) - len(image_urls_from_network)})")
            
        except Exception as e:
            print(f"[POST_PROCESSOR] Error extracting fresh URLs from page: {e}")
        
        return url_mapping
    
    def process_images_with_fresh_urls(self, html: str, staging_data_id: int, staging_data, browser_service: Optional[Any] = None) -> tuple:
        """
        Process images in HTML, using Playwright to get fresh URLs if needed.
        
        Args:
            html: HTML content
            staging_data_id: ID of the staging data record
            staging_data: AJCCStagingData model instance
            browser_service: Optional BrowserAutomationService instance
            
        Returns:
            Tuple of (updated_html, image_count)
        """
        if not html:
            return html, 0
        
        soup = BeautifulSoup(html, 'html.parser')
        images = soup.find_all('img')
        image_count = 0
        
        # First, try to extract fresh URLs from the AJCC page if we have expired URLs
        expired_urls = []
        uuid_to_old_url = {}
        
        for img in images:
            src = img.get('src', '')
            if not src:
                continue
            
            # Skip already processed images
            if 'cloudinary' in src or 'res.cloudinary.com' in src:
                continue
            
            # Check for expired heretto.com URLs
            if 'ajcc.deploy.heretto.com' in src:
                uuid_match = re.search(r'/object/([a-f0-9\-]+)', src)
                if uuid_match:
                    object_uuid = uuid_match.group(1)
                    expired_urls.append(src)
                    uuid_to_old_url[object_uuid] = src
        
        # If we have expired URLs and browser service, extract fresh URLs
        fresh_url_mapping = {}
        if expired_urls and browser_service and PLAYWRIGHT_AVAILABLE:
            print(f"[POST_PROCESSOR] Found {len(expired_urls)} expired URLs, extracting fresh URLs from AJCC page...")
            fresh_url_mapping = self.extract_fresh_image_urls_from_page(staging_data, browser_service)
        
        # Process each image
        for img in images:
            src = img.get('src', '')
            if not src:
                continue
                
            # Skip already processed images
            if 'cloudinary' in src or 'res.cloudinary.com' in src:
                continue
                
            # Skip data URLs
            if src.startswith('data:'):
                continue
            
            # Check if this is an expired URL that we have a fresh version for
            fresh_url = None
            if 'ajcc.deploy.heretto.com' in src:
                uuid_match = re.search(r'/object/([a-f0-9\-]+)', src)
                if uuid_match:
                    object_uuid = uuid_match.group(1)
                    if object_uuid in fresh_url_mapping:
                        fresh_url = fresh_url_mapping[object_uuid]
                        print(f"[POST_PROCESSOR] ✓ Found fresh URL for UUID {object_uuid}, replacing expired URL")
                    else:
                        print(f"[POST_PROCESSOR] ✗ No fresh URL found for UUID {object_uuid}, will try expired URL (may fail)")
            
            # Use fresh URL if available, otherwise use original
            url_to_download = fresh_url if fresh_url else src
            if fresh_url:
                print(f"[POST_PROCESSOR] Attempting to download using fresh URL: {url_to_download[:100]}...")
            
            # Process AJCC CDN images
            if ('ajccstaging.org' in url_to_download or 
                'ajcc.deploy.heretto.com' in url_to_download or 
                url_to_download.startswith('/')):
                try:
                    new_url = self.upload_image_to_cloudinary(
                        url_to_download, 
                        staging_data_id,
                        self.session
                    )
                    if new_url:
                        img['src'] = new_url
                        img['data-original-src'] = src  # Keep original for reference
                        image_count += 1
                        print(f"[POST_PROCESSOR] ✓ Successfully uploaded image to Cloudinary: {new_url[:80]}...")
                    else:
                        print(f"[POST_PROCESSOR] ✗ Failed to upload image (upload_image_to_cloudinary returned None)")
                except Exception as e:
                    print(f"[POST_PROCESSOR] ✗ Error uploading image {url_to_download[:100]}: {e}")
        
        return str(soup), image_count
    
    def upload_image_to_cloudinary(self, image_url: str, staging_data_id: int, session: Optional[requests.Session] = None) -> Optional[str]:
        """
        Download an image and upload it to Cloudinary.
        
        Args:
            image_url: Source URL of the image
            staging_data_id: ID for organizing in Cloudinary
            session: Optional authenticated requests.Session for downloading (uses self.session if not provided)
            
        Returns:
            Cloudinary URL or None if failed
        """
        if not CLOUDINARY_AVAILABLE:
            print("[POST_PROCESSOR] Cloudinary not available")
            return None
            
        if not REQUESTS_AVAILABLE:
            print("[POST_PROCESSOR] Requests not available")
            return None
        
        # Use provided session or fall back to instance session
        download_session = session if session else self.session
        
        # Check cache
        url_hash = hashlib.md5(image_url.encode()).hexdigest()
        if url_hash in self.image_cache:
            return self.image_cache[url_hash]
        
        try:
            # Make URL absolute if needed
            if image_url.startswith('/'):
                image_url = f"https://ajccstaging.org{image_url}"
            elif 'ajcc.deploy.heretto.com' in image_url and not image_url.startswith('https://'):
                # Ensure heretto URLs are absolute
                if not image_url.startswith('http'):
                    image_url = f"https://{image_url}"
            
            # Extract object UUID from ajcc.deploy.heretto.com URLs for better naming
            object_uuid = None
            if 'ajcc.deploy.heretto.com' in image_url:
                # Extract UUID from URL pattern: .../object/{uuid}?jwt=...
                uuid_match = re.search(r'/object/([a-f0-9\-]+)', image_url)
                if uuid_match:
                    object_uuid = uuid_match.group(1)
            
            # Download image using authenticated session
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = download_session.get(image_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Generate public ID - use UUID if available for better organization
            if object_uuid:
                public_id = f"{self.cloudinary_folder}/{object_uuid}"
            else:
                public_id = f"{self.cloudinary_folder}/staging_{staging_data_id}/{url_hash}"
            
            # Upload to Cloudinary with tags
            result = cloudinary.uploader.upload(
                response.content,
                public_id=public_id,
                resource_type='image',
                overwrite=True,
                tags=['ajcc', 'tnm', 'figure']
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
