#!/usr/bin/env python3
"""
Download AJCC Figures Script

This script authenticates with AJCC using Playwright, then processes all database records
to download AJCC figures (including those with expiring JWT tokens) and upload them to Cloudinary.
The database is updated with persistent Cloudinary URLs.

Usage:
    python scripts/download_ajcc_figures.py
"""

import os
import sys

# Load environment variables (optional)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available, assume environment variables are already set
    pass

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from models import db, AJCCStagingData, Case
import cloudinary
import cloudinary.uploader
from ajcc_tnm.services.auth_service import AJCCAuthSession
from ajcc_tnm.services.post_processor import PostProcessor
from browser_automation_service import BrowserAutomationService

# Initialize Flask app for database context
app = Flask(__name__)

# Get database URL - use same logic as app.py
DATABASE_URL = (
    os.getenv('DATABASE_POSTGRES_URL_NON_POOLING')
    or os.getenv('POSTGRES_URL_NON_POOLING')
    or os.getenv('DATABASE_URL')
    or os.getenv('POSTGRES_URL')
    or os.getenv('DATABASE_POSTGRES_URL')
)

if DATABASE_URL:
    # PostgreSQL
    db_uri = DATABASE_URL.replace('postgres://', 'postgresql://')
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
else:
    # SQLite - use absolute path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(project_root, 'instance', 'frcr_examiner.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
    secure=True
)

db.init_app(app)


def process_case_discussion(case, processor):
    """Process images in Case discussion field."""
    if not case.discussion:
        return 0
    
    try:
        updated_html, image_count = processor.process_images_in_html(
            case.discussion,
            case.id,
            processor.session
        )
        case.discussion = updated_html
        return image_count
    except Exception as e:
        print(f"[ERROR] Error processing Case {case.id} discussion: {e}")
        return 0


def main():
    """Main function to download and process all AJCC figures."""
    print("=" * 80)
    print("AJCC Figures Download Script")
    print("=" * 80)
    
    # Step 1: Authenticate with AJCC using Playwright
    print("\n[1/4] Authenticating with AJCC...")
    auth_session = AJCCAuthSession()
    
    if not auth_session.authenticate_ajcc():
        print("[ERROR] Failed to authenticate with AJCC. Please check credentials.")
        return 1
    
    authenticated_session = auth_session.get_authenticated_session()
    print("[OK] Authentication successful")
    
    # Step 2: Initialize BrowserAutomationService and PostProcessor
    print("\n[2/4] Initializing BrowserAutomationService and PostProcessor...")
    
    # Create browser service and transfer cookies from authenticated session
    browser_service = BrowserAutomationService(headless=True)
    browser_service.__enter__()
    
    # Transfer cookies from authenticated session to browser
    try:
        cookies_to_add = []
        for cookie in authenticated_session.cookies:
            cookie_dict = {
                'name': cookie.name,
                'value': cookie.value,
                'domain': cookie.domain if cookie.domain else '.ajccstaging.org',
                'path': cookie.path if cookie.path else '/',
            }
            # Add secure and httpOnly if available
            if hasattr(cookie, 'secure'):
                cookie_dict['secure'] = cookie.secure
            if hasattr(cookie, 'expires') and cookie.expires:
                cookie_dict['expires'] = cookie.expires
            cookies_to_add.append(cookie_dict)
        
        if cookies_to_add:
            browser_service.context.add_cookies(cookies_to_add)
            print(f"[OK] Transferred {len(cookies_to_add)} cookies to browser")
    except Exception as e:
        print(f"[WARNING] Could not transfer all cookies: {e}")
    
    processor = PostProcessor(authenticated_session=authenticated_session, browser_service=browser_service)
    print("[OK] PostProcessor initialized with Playwright support")
    
    # Step 3: Process all database records
    print("\n[3/4] Processing database records...")
    
    stats = {
        'staging_total': 0,
        'staging_processed': 0,
        'staging_images': 0,
        'cases_total': 0,
        'cases_processed': 0,
        'cases_images': 0,
        'errors': []
    }
    
    with app.app_context():
        # Process AJCCStagingData records
        print("\n  Processing AJCCStagingData records...")
        staging_records = AJCCStagingData.query.all()
        stats['staging_total'] = len(staging_records)
        
        for staging in staging_records:
            try:
                result = processor.process_staging_data(staging)
                stats['staging_images'] += result['images_processed']
                
                if result['success']:
                    stats['staging_processed'] += 1
                else:
                    stats['errors'].extend(result['errors'])
                
                db.session.commit()
                print(f"    [OK] Processed staging {staging.id}: {result['images_processed']} images")
                
            except Exception as e:
                print(f"    [ERROR] Error processing staging {staging.id}: {e}")
                stats['errors'].append(f"Staging {staging.id}: {str(e)}")
                db.session.rollback()
        
        # Process Case records (discussion field)
        print("\n  Processing Case records (discussion field)...")
        case_records = Case.query.filter(Case.discussion.isnot(None)).all()
        stats['cases_total'] = len(case_records)
        
        for case in case_records:
            try:
                image_count = process_case_discussion(case, processor)
                stats['cases_images'] += image_count
                
                if image_count > 0:
                    db.session.commit()
                    stats['cases_processed'] += 1
                    print(f"    [OK] Processed Case {case.id}: {image_count} images")
                
            except Exception as e:
                print(f"    [ERROR] Error processing Case {case.id}: {e}")
                stats['errors'].append(f"Case {case.id}: {str(e)}")
                db.session.rollback()
    
    # Step 4: Print summary
    print("\n[4/4] Summary")
    print("=" * 80)
    print(f"AJCCStagingData:")
    print(f"  Total records: {stats['staging_total']}")
    print(f"  Processed: {stats['staging_processed']}")
    print(f"  Images uploaded: {stats['staging_images']}")
    print(f"\nCase records:")
    print(f"  Total records with discussion: {stats['cases_total']}")
    print(f"  Processed: {stats['cases_processed']}")
    print(f"  Images uploaded: {stats['cases_images']}")
    print(f"\nTotal images uploaded: {stats['staging_images'] + stats['cases_images']}")
    
    if stats['errors']:
        print(f"\nErrors ({len(stats['errors'])}):")
        for error in stats['errors'][:10]:  # Show first 10 errors
            print(f"  - {error}")
        if len(stats['errors']) > 10:
            print(f"  ... and {len(stats['errors']) - 10} more errors")
    
    print("\n[OK] Processing complete!")
    
    # Cleanup browser service
    try:
        browser_service.__exit__(None, None, None)
    except:
        pass
    
    return 0


if __name__ == '__main__':
    exit(main())
