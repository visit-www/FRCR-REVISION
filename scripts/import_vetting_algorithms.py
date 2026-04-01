#!/usr/bin/env python3
"""
Import vetting algorithms from JSON into the VettingAlgorithm table.

Usage:
    python scripts/import_vetting_algorithms.py data/algorithms_part_1.json
    python scripts/import_vetting_algorithms.py data/algorithms_part_2.json

Input JSON format:
{
  "advanced_algorithms": [
    {
      "algorithm_id": "ACUTE_STROKE_FULL",
      "body_part": "Brain",
      "clinical_scenario": "Acute neurological deficit",
      "entry_criteria": [...],
      "steps": [...],
      "safety": {...},
      "tags": [...]
    }
  ]
}

All algorithms are imported as origin='admin', is_published=False.
Admin reviews and publishes via /vetting/admin/algorithms.
"""

import json
import re
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import VettingAlgorithm


def slugify(text):
    slug = text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug[:200]


def build_title(algorithm_id, clinical_scenario):
    """Generate a human-readable title from algorithm_id and clinical_scenario."""
    # Use clinical_scenario as the base, capitalise nicely
    title = clinical_scenario.strip()
    # Append "Imaging Pathway" if not already descriptive enough
    lower = title.lower()
    if not any(w in lower for w in ('pathway', 'workflow', 'algorithm', 'protocol')):
        title += ' Imaging Pathway'
    return title


def build_keywords(algorithm_data):
    """Extract keywords from tags, algorithm_id, and clinical_scenario."""
    parts = []
    # Tags
    parts.extend(algorithm_data.get('tags', []))
    # Algorithm ID words (split on underscore, skip 'FULL')
    id_parts = algorithm_data.get('algorithm_id', '').split('_')
    for p in id_parts:
        if p.upper() not in ('FULL', 'WORKFLOW'):
            parts.append(p.lower())
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for p in parts:
        lower = p.lower().strip()
        if lower and lower not in seen:
            seen.add(lower)
            unique.append(p.strip())
    return ', '.join(unique)


def import_algorithms(json_path):
    """Import algorithms from JSON file."""
    with open(json_path, 'r') as f:
        data = json.load(f)

    # Accept both {"advanced_algorithms": [...]} and flat [...]
    if isinstance(data, dict) and 'advanced_algorithms' in data:
        algorithms = data['advanced_algorithms']
    elif isinstance(data, list):
        algorithms = data
    else:
        print("Error: JSON must contain 'advanced_algorithms' array or be a flat array.")
        sys.exit(1)

    print(f"Found {len(algorithms)} algorithms to import from {json_path}.")

    with app.app_context():
        imported = 0
        skipped = 0

        for alg in algorithms:
            algorithm_key = (alg.get('algorithm_id') or '').strip()
            clinical_scenario = (alg.get('clinical_scenario') or '').strip()

            if not algorithm_key:
                print(f"  SKIP: missing algorithm_id: {alg}")
                skipped += 1
                continue

            # Check for duplicate by algorithm_key
            existing = VettingAlgorithm.query.filter_by(algorithm_key=algorithm_key).first()
            if existing:
                print(f"  SKIP (exists): {algorithm_key}")
                skipped += 1
                continue

            title = build_title(algorithm_key, clinical_scenario)
            body_section = (alg.get('body_part') or '').strip() or None
            entry_criteria = alg.get('entry_criteria', [])
            steps = alg.get('steps', [])
            safety = alg.get('safety', {})
            tags = ', '.join(alg.get('tags', []))

            algorithm = VettingAlgorithm(
                algorithm_key=algorithm_key,
                title=title,
                slug=slugify(title),
                body_section=body_section,
                clinical_scenario=clinical_scenario,
                entry_criteria_json=json.dumps(entry_criteria) if entry_criteria else None,
                steps_json=json.dumps(steps),
                safety_json=json.dumps(safety) if safety else None,
                tags=tags or None,
                keywords=build_keywords(alg),
                origin='admin',
                is_published=False,
            )
            db.session.add(algorithm)
            imported += 1
            print(f"  ADD: {algorithm_key} — {title}")

        db.session.commit()
        print(f"\nDone: {imported} imported, {skipped} skipped.")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_vetting_algorithms.py <algorithms.json>")
        sys.exit(1)

    json_path = sys.argv[1]
    if not os.path.isfile(json_path):
        print(f"Error: file not found: {json_path}")
        sys.exit(1)

    import_algorithms(json_path)
