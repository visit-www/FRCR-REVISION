#!/usr/bin/env python3
"""
Import imaging protocols from JSON into the ImagingProtocol table.

Usage:
    python scripts/import_imaging_protocols.py protocols.json

Input JSON format (array of protocol objects):
[
  {
    "name": "CT Pulmonary Angiography",
    "modality": "CT",
    "body_part": "Thorax",
    "is_emergency": true,
    "indication": ["PE", "Pulmonary embolism"],
    "basic_layer": {
      "study_name": "CTPA",
      "coverage": "Diaphragm to apices",
      "contrast_summary": "IV contrast, PA phase, bolus tracking"
    },
    "detailed_layer": {
      "ct_phases": [...],
      "mri_sequences": [...]
    },
    "validation": {
      "requires_egfr": true,
      "egfr_threshold": 30,
      "pregnancy_check_required": true,
      "allergy_check_required": true
    },
    "smart_tags": ["pe", "dvt", "d-dimer"],
    "search_index": {
      "keywords": ["pulmonary", "embolism"],
      "synonyms": ["ctpa", "pe study"]
    }
  }
]

All protocols are imported as origin='admin', is_published=False.
Admin reviews and publishes via /vetting/admin/protocols.
"""

import json
import re
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import ImagingProtocol


def slugify(text):
    slug = text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug[:200]


def build_shorthand(basic_layer):
    """Convert basic_layer dict to consultant shorthand text."""
    parts = []
    if basic_layer.get('study_name'):
        parts.append(basic_layer['study_name'])
    if basic_layer.get('coverage'):
        parts.append(basic_layer['coverage'])
    if basic_layer.get('contrast_summary'):
        parts.append(basic_layer['contrast_summary'])
    return '\n'.join(parts)


def build_detailed_html(detailed_layer, modality):
    """Convert detailed_layer dict to HTML table."""
    rows = []

    if modality == 'CT' and detailed_layer.get('ct_phases'):
        for phase in detailed_layer['ct_phases']:
            phase_name = phase.get('phase_name', 'Phase')
            rows.append(f'<tr class="table-light"><td colspan="2"><strong>{_esc(phase_name)}</strong></td></tr>')
            for key, val in phase.items():
                if key == 'phase_name':
                    continue
                label = key.replace('_', ' ').title()
                rows.append(f'<tr><td>{_esc(label)}</td><td>{_esc(str(val))}</td></tr>')

    elif modality == 'MRI' and detailed_layer.get('mri_sequences'):
        for seq in detailed_layer['mri_sequences']:
            seq_name = seq.get('sequence_name', 'Sequence')
            rows.append(f'<tr class="table-light"><td colspan="2"><strong>{_esc(seq_name)}</strong></td></tr>')
            for key, val in seq.items():
                if key == 'sequence_name':
                    continue
                label = key.replace('_', ' ').title()
                rows.append(f'<tr><td>{_esc(label)}</td><td>{_esc(str(val))}</td></tr>')

    else:
        # Generic fallback: render all key-value pairs
        for key, val in detailed_layer.items():
            if isinstance(val, (list, dict)):
                val = json.dumps(val, indent=2)
            label = key.replace('_', ' ').title()
            rows.append(f'<tr><td>{_esc(label)}</td><td>{_esc(str(val))}</td></tr>')

    if not rows:
        return ''

    html = (
        "<table class='table table-sm vetting-protocol-table'>"
        "<thead><tr><th>Parameter</th><th>Value</th></tr></thead>"
        "<tbody>" + ''.join(rows) + "</tbody></table>"
        "<p class='text-muted small mt-2'><em>Verify parameters for your department.</em></p>"
    )
    return html


def build_keywords(protocol_data):
    """Combine smart_tags, search_index keywords, and synonyms into comma-separated string."""
    parts = []
    parts.extend(protocol_data.get('smart_tags', []))
    search_index = protocol_data.get('search_index', {})
    parts.extend(search_index.get('keywords', []))
    parts.extend(search_index.get('synonyms', []))
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for p in parts:
        lower = p.lower().strip()
        if lower and lower not in seen:
            seen.add(lower)
            unique.append(p.strip())
    return ', '.join(unique)


def _esc(text):
    """Escape HTML special characters."""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def import_protocols(json_path):
    """Import protocols from JSON file."""
    with open(json_path, 'r') as f:
        protocols = json.load(f)

    # Accept both {"protocols": [...]} and flat [...]
    if isinstance(protocols, dict) and 'protocols' in protocols:
        protocols = protocols['protocols']
    if not isinstance(protocols, list):
        print("Error: JSON must be an array of protocol objects (or {\"protocols\": [...]}).")
        sys.exit(1)

    print(f"Found {len(protocols)} protocols to import.")

    with app.app_context():
        imported = 0
        skipped = 0

        for p in protocols:
            name = p.get('name', '').strip()
            modality = p.get('modality', '').strip()

            if not name or not modality:
                print(f"  SKIP: missing name or modality: {p}")
                skipped += 1
                continue

            # Check for duplicate by title + modality
            existing = ImagingProtocol.query.filter_by(
                title=name, modality=modality, origin='admin'
            ).first()
            if existing:
                print(f"  SKIP (exists): {name} ({modality})")
                skipped += 1
                continue

            basic_layer = p.get('basic_layer', {})
            detailed_layer = p.get('detailed_layer', {})

            protocol = ImagingProtocol(
                title=name,
                slug=slugify(name),
                modality=modality,
                body_section=p.get('body_part', '').strip() or None,
                keywords=build_keywords(p),
                shorthand_text=build_shorthand(basic_layer),
                detailed_protocol_html=build_detailed_html(detailed_layer, modality),
                special_notes=p.get('special_notes', '').strip() or None,
                indication_json=json.dumps(p.get('indication', [])),
                validation_json=json.dumps(p.get('validation', {})),
                search_config_json=json.dumps(p.get('search_index', {})),
                origin='admin',
                is_published=False,
                is_emergency=p.get('is_emergency', False),
            )
            db.session.add(protocol)
            imported += 1
            print(f"  ADD: {name} ({modality})")

        db.session.commit()
        print(f"\nDone: {imported} imported, {skipped} skipped.")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_imaging_protocols.py <protocols.json>")
        sys.exit(1)

    json_path = sys.argv[1]
    if not os.path.isfile(json_path):
        print(f"Error: file not found: {json_path}")
        sys.exit(1)

    import_protocols(json_path)
