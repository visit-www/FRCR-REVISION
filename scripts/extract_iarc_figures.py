#!/usr/bin/env python3
"""
IARC Essential TNM Figure Extraction Script

Extracts figures from the IARC Essential TNM Guide PDF,
uploads them to Cloudinary, and populates the database.

Usage:
    python scripts/extract_iarc_figures.py

Requirements:
    pip install PyMuPDF cloudinary pillow

License: IARC Essential TNM Guide is CC BY-NC-ND 3.0 IGO
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Error: PyMuPDF not installed. Run: pip install PyMuPDF")
    sys.exit(1)

try:
    import cloudinary
    import cloudinary.uploader
except ImportError:
    print("Error: cloudinary not installed. Run: pip install cloudinary")
    sys.exit(1)

# Configuration
IARC_PDF_PATH = "/Users/zen/Library/CloudStorage/OneDrive-Personal/Workstation companions/IARC_TNM_Essentia.pdf"
OUTPUT_DIR = "/Users/zen/myRepos/projects/FRCR_REVISION/scripts/iarc_figures"
CLOUDINARY_FOLDER = "frcr_revision/anatomy/iarc"

# Attribution string (required for CC BY-NC-ND 3.0 IGO)
ATTRIBUTION = "IARC Essential TNM Guide (CC BY-NC-ND 3.0 IGO)"
LICENSE = "CC BY-NC-ND 3.0 IGO"

# Cancer type mapping based on PDF page ranges (to be populated after review)
# Format: (start_page, end_page, cancer_type, staging_category)
CANCER_PAGE_RANGES = {
    # These will be populated after manual review of PDF
    # Example:
    # (10, 15): ("breast", "general"),
    # (16, 20): ("lung", "general"),
}


def setup_cloudinary():
    """Configure Cloudinary from environment variables."""
    cloudinary.config(
        cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
        api_key=os.environ.get('CLOUDINARY_API_KEY'),
        api_secret=os.environ.get('CLOUDINARY_API_SECRET')
    )
    
    if not os.environ.get('CLOUDINARY_CLOUD_NAME'):
        print("Warning: Cloudinary not configured. Images will be saved locally only.")
        return False
    return True


def extract_images_from_pdf(pdf_path: str, output_dir: str) -> list:
    """
    Extract all images from the IARC PDF.
    
    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save extracted images
        
    Returns:
        List of extracted image metadata
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    doc = fitz.open(pdf_path)
    extracted_images = []
    
    print(f"Processing {len(doc)} pages...")
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images()
        
        for img_index, img in enumerate(image_list):
            xref = img[0]
            
            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                
                # Skip very small images (likely icons)
                if len(image_bytes) < 5000:
                    continue
                
                # Generate unique ID
                image_hash = hashlib.md5(image_bytes).hexdigest()[:12]
                figure_id = f"iarc_p{page_num+1}_i{img_index}_{image_hash}"
                filename = f"{figure_id}.{image_ext}"
                filepath = os.path.join(output_dir, filename)
                
                # Save locally
                with open(filepath, "wb") as f:
                    f.write(image_bytes)
                
                # Get image dimensions
                width = base_image.get("width", 0)
                height = base_image.get("height", 0)
                
                # Determine cancer type from page number (if mapped)
                cancer_type = None
                staging_category = None
                for (start, end), (ctype, scat) in CANCER_PAGE_RANGES.items():
                    if start <= page_num + 1 <= end:
                        cancer_type = ctype
                        staging_category = scat
                        break
                
                extracted_images.append({
                    'figure_id': figure_id,
                    'page_number': page_num + 1,
                    'image_index': img_index,
                    'filename': filename,
                    'filepath': filepath,
                    'format': image_ext,
                    'size_bytes': len(image_bytes),
                    'width': width,
                    'height': height,
                    'cancer_type': cancer_type,
                    'staging_category': staging_category,
                    'title': f"IARC TNM Figure - Page {page_num + 1}",
                    'attribution': ATTRIBUTION,
                    'license': LICENSE
                })
                
                print(f"  Extracted: {filename} ({width}x{height}, {len(image_bytes)} bytes)")
                
            except Exception as e:
                print(f"  Error extracting image {img_index} from page {page_num + 1}: {e}")
    
    doc.close()
    return extracted_images


def upload_to_cloudinary(images: list) -> list:
    """
    Upload extracted images to Cloudinary.
    
    Args:
        images: List of image metadata from extract_images_from_pdf
        
    Returns:
        Updated list with Cloudinary URLs
    """
    if not setup_cloudinary():
        print("Skipping Cloudinary upload - not configured")
        return images
    
    print(f"\nUploading {len(images)} images to Cloudinary...")
    
    for img in images:
        try:
            public_id = f"{CLOUDINARY_FOLDER}/{img['figure_id']}"
            
            result = cloudinary.uploader.upload(
                img['filepath'],
                public_id=public_id,
                resource_type='image',
                overwrite=True,
                tags=['iarc', 'tnm', 'staging', 'anatomy']
            )
            
            img['cloudinary_url'] = result.get('secure_url')
            img['cloudinary_public_id'] = result.get('public_id')
            
            # Generate thumbnail
            thumbnail_url = cloudinary.CloudinaryImage(public_id).build_url(
                width=200,
                height=200,
                crop='fit'
            )
            img['thumbnail_url'] = thumbnail_url
            
            print(f"  Uploaded: {img['figure_id']} -> {img['cloudinary_url']}")
            
        except Exception as e:
            print(f"  Error uploading {img['figure_id']}: {e}")
            img['cloudinary_url'] = None
    
    return images


def save_metadata(images: list, output_file: str):
    """Save image metadata to JSON file for database import."""
    with open(output_file, 'w') as f:
        json.dump(images, f, indent=2)
    print(f"\nMetadata saved to: {output_file}")


def populate_database(images: list):
    """
    Populate the AnatomyFigure database table.
    
    Requires Flask app context.
    """
    from app import app
    from models import db, AnatomyFigure
    
    with app.app_context():
        added = 0
        updated = 0
        
        for img in images:
            if not img.get('cloudinary_url'):
                continue
            
            # Check if figure already exists
            existing = AnatomyFigure.query.filter_by(figure_id=img['figure_id']).first()
            
            if existing:
                # Update existing
                existing.cloudinary_url = img['cloudinary_url']
                existing.cloudinary_public_id = img.get('cloudinary_public_id')
                existing.thumbnail_url = img.get('thumbnail_url')
                existing.updated_at = datetime.utcnow()
                updated += 1
            else:
                # Create new
                figure = AnatomyFigure(
                    figure_id=img['figure_id'],
                    title=img.get('title', f"IARC Figure {img['figure_id']}"),
                    description=f"Extracted from IARC Essential TNM Guide, page {img['page_number']}",
                    source='iarc',
                    body_region=None,  # To be manually categorized
                    figure_type='staging',
                    keywords=[],  # To be manually populated
                    cancer_type=img.get('cancer_type'),
                    staging_category=img.get('staging_category'),
                    original_url=None,  # PDF extraction, no URL
                    cloudinary_url=img['cloudinary_url'],
                    cloudinary_public_id=img.get('cloudinary_public_id'),
                    thumbnail_url=img.get('thumbnail_url'),
                    license=LICENSE,
                    attribution=ATTRIBUTION,
                    page_number=img['page_number'],
                    is_active=True
                )
                db.session.add(figure)
                added += 1
        
        db.session.commit()
        print(f"\nDatabase updated: {added} added, {updated} updated")


def main():
    """Main extraction workflow."""
    print("=" * 60)
    print("IARC Essential TNM Figure Extraction")
    print("=" * 60)
    
    # Check PDF exists
    if not os.path.exists(IARC_PDF_PATH):
        print(f"Error: PDF not found at {IARC_PDF_PATH}")
        sys.exit(1)
    
    print(f"\nPDF: {IARC_PDF_PATH}")
    print(f"Output: {OUTPUT_DIR}")
    
    # Step 1: Extract images
    print("\n[Step 1] Extracting images from PDF...")
    images = extract_images_from_pdf(IARC_PDF_PATH, OUTPUT_DIR)
    print(f"Extracted {len(images)} images")
    
    # Step 2: Upload to Cloudinary
    print("\n[Step 2] Uploading to Cloudinary...")
    images = upload_to_cloudinary(images)
    
    # Step 3: Save metadata
    metadata_file = os.path.join(OUTPUT_DIR, "iarc_figures_metadata.json")
    save_metadata(images, metadata_file)
    
    # Step 4: Populate database (optional)
    print("\n[Step 4] Database population...")
    try:
        populate_database(images)
    except Exception as e:
        print(f"Database population skipped: {e}")
        print("Run 'flask shell' and import manually if needed.")
    
    print("\n" + "=" * 60)
    print("Extraction complete!")
    print(f"Images saved to: {OUTPUT_DIR}")
    print(f"Metadata saved to: {metadata_file}")
    print("\nNext steps:")
    print("1. Review extracted images and delete irrelevant ones")
    print("2. Update CANCER_PAGE_RANGES mapping for accurate categorization")
    print("3. Re-run script to update database with categories")
    print("=" * 60)


if __name__ == "__main__":
    main()
