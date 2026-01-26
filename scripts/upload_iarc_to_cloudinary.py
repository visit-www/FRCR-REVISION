#!/usr/bin/env python3
"""
Upload IARC Essential TNM figures to Cloudinary.

Reads from static/essential_tnm_data.json, uploads images,
and updates the JSON with Cloudinary URLs.
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cloudinary
import cloudinary.uploader

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)

CLOUDINARY_FOLDER = "frcr_revision/essential_tnm"
IARC_FIGURES_DIR = Path(__file__).parent / "iarc_figures"
ESSENTIAL_TNM_JSON = Path(__file__).parent.parent / "static" / "essential_tnm_data.json"


def upload_figure(filepath: str, figure_id: str) -> dict:
    """Upload a single figure to Cloudinary."""
    try:
        public_id = f"{CLOUDINARY_FOLDER}/{figure_id}"
        
        result = cloudinary.uploader.upload(
            filepath,
            public_id=public_id,
            resource_type='image',
            overwrite=True,
            tags=['iarc', 'tnm', 'essential_tnm', 'staging']
        )
        
        print(f"  ✓ Uploaded: {figure_id}")
        
        return {
            'cloudinary_url': result.get('secure_url'),
            'cloudinary_public_id': result.get('public_id'),
            'thumbnail_url': cloudinary.CloudinaryImage(public_id).build_url(
                width=200, height=200, crop='fit'
            )
        }
    except Exception as e:
        print(f"  ✗ Error uploading {figure_id}: {e}")
        return {}


def main():
    print("=" * 60)
    print("IARC Essential TNM Figure Upload to Cloudinary")
    print("=" * 60)
    
    # Check Cloudinary config
    if not os.environ.get('CLOUDINARY_CLOUD_NAME'):
        print("ERROR: CLOUDINARY_CLOUD_NAME not set")
        sys.exit(1)
    
    print(f"\nCloud: {os.environ.get('CLOUDINARY_CLOUD_NAME')}")
    print(f"Folder: {CLOUDINARY_FOLDER}")
    print(f"Source: {IARC_FIGURES_DIR}")
    
    # Load essential_tnm_data.json
    if not ESSENTIAL_TNM_JSON.exists():
        print(f"ERROR: {ESSENTIAL_TNM_JSON} not found")
        sys.exit(1)
    
    with open(ESSENTIAL_TNM_JSON, 'r') as f:
        data = json.load(f)
    
    print(f"\nProcessing {len(data)} entries...")
    
    updated = 0
    for entry in data:
        figure_id = entry.get('figure_id')
        filename = entry.get('filename')
        
        if not figure_id or not filename:
            continue
        
        # Find the image file
        filepath = IARC_FIGURES_DIR / filename
        if not filepath.exists():
            # Try alternative locations
            alt_paths = [
                IARC_FIGURES_DIR / f"{figure_id}.jpeg",
                IARC_FIGURES_DIR / f"{figure_id}.jpg",
                IARC_FIGURES_DIR / f"{figure_id}.png",
            ]
            for alt in alt_paths:
                if alt.exists():
                    filepath = alt
                    break
        
        if not filepath.exists():
            print(f"  ⚠ File not found: {filename}")
            continue
        
        # Upload to Cloudinary
        result = upload_figure(str(filepath), figure_id)
        
        if result:
            entry['cloudinary_url'] = result.get('cloudinary_url')
            entry['cloudinary_public_id'] = result.get('cloudinary_public_id')
            entry['thumbnail_url'] = result.get('thumbnail_url')
            updated += 1
    
    # Save updated JSON
    with open(ESSENTIAL_TNM_JSON, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\n{'=' * 60}")
    print(f"Upload complete: {updated} figures uploaded")
    print(f"Updated: {ESSENTIAL_TNM_JSON}")
    print("=" * 60)


if __name__ == "__main__":
    main()
