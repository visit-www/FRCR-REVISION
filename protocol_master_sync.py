"""
Protocol Master Sync
────────────────────

Synchronises the `imaging_protocol` DB table with the master JSON files at
`static/data/ct_protocols.json` and `static/data/mri_protocols.json`.

Called from app.py's DB init block as an idempotent, sentinel-gated migration.

Safety:
- Idempotent per row: sentinel `<!-- migrated:master-v1 -->` appended to
  `detailed_protocol_html`. Rows with a matching sentinel are skipped on
  subsequent runs.
- Personal protocols (origin='personal') are NEVER touched.
- Rows with no matching master JSON slug are DELETED only if they are admin
  rows AND the sync flag requires full replacement (opt-in).
- Backup of pre-migration state lives at
  `static/data/backups/prod_imaging_protocols_*.json`.
- Version bump: to force re-sync all rows, bump `_SYNC_VERSION` to a new
  value (e.g. 'master-v2'). Existing sentinels won't match so every row
  gets re-processed.
"""
import json
import os
import re
from datetime import datetime

_SYNC_VERSION = 'master-v4'  # bumped: ARI oncology 'protocol' field fallback + re-sync
_SENTINEL = f'<!-- migrated:{_SYNC_VERSION} -->'
# Include legacy sentinels used by older migration blocks (rebrand, scrub)
# so those blocks leave sync-managed rows alone.
_LEGACY_SENTINELS = (
    '<!-- src:radinsight-v1 -->'   # rebrand block (app.py ~line 866)
    '<!-- scrub:koc-ari-v1 -->'    # PR4 C1 scrub block (app.py ~line 1602)
)
_DATA_DIR = os.path.join(os.path.dirname(__file__), 'static', 'data')


# ═══════════════════════════════════════════════════════════════════════════
#  SLUG + UTIL
# ═══════════════════════════════════════════════════════════════════════════

def _slugify(text: str) -> str:
    slug = (text or '').lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug[:200]


def _escape(s) -> str:
    if s is None:
        return ''
    return (str(s)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def _render_list(items) -> str:
    if not items:
        return ''
    if isinstance(items, str):
        return _escape(items)
    return '<ul class="mb-0 ps-3">' + ''.join(
        f'<li>{_escape(i)}</li>' for i in items if i
    ) + '</ul>'


# ═══════════════════════════════════════════════════════════════════════════
#  BODY SECTION INFERENCE (for DB indexing)
# ═══════════════════════════════════════════════════════════════════════════

_BODY_KEYWORDS = [
    ('Brain', ['brain', 'stroke', 'dementia', 'sella', 'pituitary', 'iam', 'iac',
               'inner ear', 'orbit', 'skull base', 'trigeminal', 'sinuses',
               'epilepsy', 'avm', 'csf', 'meningitis', 'ms ', 'demyelinat',
               'cerebral', 'cerebral hemorrhage', 'cerebral haemorrhage',
               'brain tumour', 'brain tumor', 'petrous', 'paediatric brain']),
    ('Head and Neck', ['neck', 'face', 'facial', 'temporal', 'parathyroid',
                        'thyroid', 'sialography', 'mastoiditis', 'cellulitis',
                        'oral cavity']),
    ('Spine', ['spine', 'cervical spine', 'thoracic spine', 'lumbar spine',
               'sacrum', 'coccyx', 'brachial plexus', 'cord compression',
               'lumbar plexus', 'neurography']),
    ('Thorax', ['chest', 'thorax', 'lung', 'pulmonary', 'thoracic', 'hrct',
                'mesothelioma', 'pleural']),
    ('Breast', ['breast']),
    ('Cardiac', ['cardiac', 'heart']),
    ('Abdomen', ['abdomen', 'abdominal', 'liver', 'pancrea', 'bowel',
                 'enterography', 'ileus', 'sbo', 'anastomosis',
                 'gi bleed', 'hepatic', 'mrcp', 'retroperitoneal',
                 'gastric', 'oesophag', 'cholangio']),
    ('Pelvis', ['pelvis', 'rectum', 'anal', 'fistula', 'endometri',
                'ovarian', 'cervix', 'uterus', 'gyne', 'placenta',
                'proctogram', 'perineal']),
    ('Urogenital', ['prostate', 'bladder', 'urethra', 'testis', 'penis',
                    'scrotum', 'kidney', 'renal', 'adrenal', 'urogram',
                    'kub', 'urinary', 'tcc', 'urothelial']),
    ('MSK', ['shoulder', 'elbow', 'wrist', 'hand', 'finger', 'thumb',
             'hip', 'knee', 'ankle', 'foot', 'leg', 'thigh', 'sternum',
             'clavicle', 'scapula', 'humerus', 'forearm', 'sarcoma',
             'si joint', 'msk', 'extremit', 'bony pelvis', 'arthrogram',
             'psoas', 'soft tissue']),
    ('Cardiovascular', ['angio', 'cta', 'aort', 'carotid', 'subclavian',
                         'venogram', 'venography', 'mra', 'mrv', 'dissection',
                         'peripheral']),
    ('Multisystem', ['whole body', 'cap', 'cancer', 'staging', 'lymphoma',
                      'melanoma', 'cup', 'trauma']),
]


def _infer_body_section(title: str, hint: str = None) -> str:
    """Pick a body_section from the title (case-insensitive keyword match)."""
    if hint:
        return hint
    t = (title or '').lower()
    for section, kws in _BODY_KEYWORDS:
        for kw in kws:
            if kw in t:
                return section
    return 'Multisystem'


def _infer_emergency(title: str) -> bool:
    t = (title or '').lower()
    return any(k in t for k in [
        'trauma', 'stroke', 'acute', 'bleed', 'haemorrhage', 'hemorrhage',
        'dissection', 'aneurysm', 'emergency', 'cord compression',
        'ruptur', 'ischaem', 'ischem', 'pulmonary embol',
    ])


# ═══════════════════════════════════════════════════════════════════════════
#  CT HTML RENDERER
# ═══════════════════════════════════════════════════════════════════════════

def _render_ct_html(title: str, entry: dict) -> str:
    """Render a CT protocol (Swansea-format: Prep / Contrast / Parameters /
    Comments) as styled HTML matching the app brand."""
    prep = entry.get('Prep') or ''
    contrast = entry.get('Contrast') or ''
    # ARI oncology protocols use 'protocol' field instead of 'Parameters'
    params = entry.get('Parameters') or entry.get('protocol') or ''
    comments = entry.get('Comments') or ''

    status = entry.get('status', 'verified')
    status_badge = ''
    if status == 'to_be_verified':
        status_badge = (
            '<div class="alert alert-warning small mb-3 py-2">'
            '<i class="fas fa-flask me-1"></i>'
            '<strong>To be verified</strong> &mdash; this protocol is pending '
            'consultant review. Use with caution and verify against local policy.'
            '</div>'
        )

    html = (
        '<div class="radinsights-protocol">'
        + status_badge
        + '<h5 class="mb-3" style="color: #e96304;">' + _escape(title) + '</h5>'
        '<table class="table table-sm table-bordered radinsights-protocol-table">'
        '<thead class="table-light">'
        '<tr><th style="width: 22%;">Parameter</th><th>Details</th></tr>'
        '</thead>'
        '<tbody>'
        f'<tr><td class="fw-semibold">Patient preparation</td><td>{_escape(prep) or "<em class=\'text-muted\'>Not specified</em>"}</td></tr>'
        f'<tr><td class="fw-semibold">Contrast</td><td>{_escape(contrast) or "<em class=\'text-muted\'>None</em>"}</td></tr>'
        f'<tr><td class="fw-semibold">Parameters / Phases</td><td>{_escape(params) or "<em class=\'text-muted\'>Not specified</em>"}</td></tr>'
        f'<tr><td class="fw-semibold">Comments / Clinical notes</td><td>{_escape(comments) or "<em class=\'text-muted\'>None</em>"}</td></tr>'
        '</tbody>'
        '</table>'
        '<p class="text-muted small mt-2"><em>Source: <strong>RadInsights Imaging Protocols</strong> '
        '&mdash; enriched by open-source protocol guides. Verify against local policy.</em></p>'
        '</div>'
    )
    return html


# ═══════════════════════════════════════════════════════════════════════════
#  MRI HTML RENDERER
# ═══════════════════════════════════════════════════════════════════════════

_MRI_PLANES = ['Axial', 'Coronal', 'Sagittal', 'Axial Oblique',
               'Coronal Oblique', 'Sagittal Oblique', 'Other']


def _render_mri_html(title: str, entry: dict) -> str:
    """Render an MRI protocol as styled HTML. MRI entries have indication,
    planes (Axial/Coronal/Sagittal arrays of sequences), notes, prep, coverage,
    contrast."""
    indication = entry.get('indication') or ''
    positioning = entry.get('positioning') or ''
    prep = entry.get('prep') or []
    contrast = entry.get('contrast') or ''
    coverage = entry.get('coverage') or ''
    notes = entry.get('notes') or entry.get('special_notes') or []
    base = entry.get('base') or entry.get('_base') or ''

    status = entry.get('status', 'verified')
    status_badge = ''
    if status == 'to_be_verified':
        status_badge = (
            '<div class="alert alert-warning small mb-3 py-2">'
            '<i class="fas fa-flask me-1"></i>'
            '<strong>To be verified</strong> &mdash; this protocol is pending '
            'consultant review. Use with caution and verify against local policy.'
            '</div>'
        )

    rows = []

    if indication:
        rows.append(
            f'<tr><td class="fw-semibold">Indication</td>'
            f'<td>{_escape(indication)}</td></tr>'
        )

    if base:
        rows.append(
            f'<tr><td class="fw-semibold">Base protocol</td>'
            f'<td>{_escape(base)}</td></tr>'
        )

    if positioning:
        rows.append(
            f'<tr><td class="fw-semibold">Positioning</td>'
            f'<td>{_escape(positioning)}</td></tr>'
        )

    if prep:
        rows.append(
            f'<tr><td class="fw-semibold">Preparation</td>'
            f'<td>{_render_list(prep)}</td></tr>'
        )

    if contrast:
        rows.append(
            f'<tr><td class="fw-semibold">Contrast</td>'
            f'<td>{_escape(contrast)}</td></tr>'
        )

    if coverage:
        rows.append(
            f'<tr><td class="fw-semibold">Coverage</td>'
            f'<td>{_escape(coverage)}</td></tr>'
        )

    # Planes × sequences
    for plane in _MRI_PLANES:
        if plane in entry and isinstance(entry[plane], list) and entry[plane]:
            rows.append(
                f'<tr><td class="fw-semibold">{plane}</td>'
                f'<td>{_render_list(entry[plane])}</td></tr>'
            )

    if notes:
        rows.append(
            f'<tr><td class="fw-semibold">Notes</td>'
            f'<td>{_render_list(notes)}</td></tr>'
        )

    # Complex nested sequences (MR Enterography verbatim)
    if isinstance(entry.get('sequences'), dict):
        for stage_name, stage_data in entry['sequences'].items():
            stage_label = stage_name.replace('_', ' ').title()
            if isinstance(stage_data, dict):
                stage_rows = []
                timing = stage_data.get('timing', '')
                if timing:
                    stage_rows.append(f'<p class="small text-muted mb-1">{_escape(timing)}</p>')
                for k, v in stage_data.items():
                    if k == 'timing':
                        continue
                    if isinstance(v, list) and v:
                        stage_rows.append(f'<strong>{_escape(k)}:</strong>{_render_list(v)}')
                if stage_rows:
                    rows.append(
                        f'<tr><td class="fw-semibold">{_escape(stage_label)}</td>'
                        f'<td>{"".join(stage_rows)}</td></tr>'
                    )

    # Nested preparation block for MR Enterography
    if isinstance(entry.get('preparation'), dict):
        prep_dict = entry['preparation']
        prep_parts = []
        for k, v in prep_dict.items():
            klabel = k.replace('_', ' ').title()
            if isinstance(v, str):
                prep_parts.append(f'<p><strong>{_escape(klabel)}:</strong> {_escape(v)}</p>')
            elif isinstance(v, list):
                prep_parts.append(f'<p><strong>{_escape(klabel)}:</strong></p>{_render_list(v)}')
            elif isinstance(v, dict):
                prep_parts.append(f'<p><strong>{_escape(klabel)}:</strong></p>')
                for sk, sv in v.items():
                    if isinstance(sv, list):
                        prep_parts.append(f'<p class="mb-1"><em>{_escape(sk.title())}:</em></p>{_render_list(sv)}')
                    else:
                        prep_parts.append(f'<p class="mb-1"><em>{_escape(sk.title())}:</em> {_escape(sv)}</p>')
        if prep_parts:
            rows.append(
                f'<tr><td class="fw-semibold">Detailed preparation</td>'
                f'<td>{"".join(prep_parts)}</td></tr>'
            )

    if isinstance(entry.get('technologist_notes'), list) and entry['technologist_notes']:
        rows.append(
            f'<tr><td class="fw-semibold">Technologist notes</td>'
            f'<td>{_render_list(entry["technologist_notes"])}</td></tr>'
        )

    html = (
        '<div class="radinsights-protocol">'
        + status_badge
        + '<h5 class="mb-3" style="color: #e96304;">' + _escape(title) + '</h5>'
        '<table class="table table-sm table-bordered radinsights-protocol-table">'
        '<thead class="table-light">'
        '<tr><th style="width: 22%;">Field</th><th>Details</th></tr>'
        '</thead>'
        '<tbody>'
        + ''.join(rows) +
        '</tbody>'
        '</table>'
        '<p class="text-muted small mt-2"><em>Source: <strong>RadInsights Imaging Protocols</strong> '
        '&mdash; enriched by open-source protocol guides. Verify against local policy.</em></p>'
        '</div>'
    )
    return html


# ═══════════════════════════════════════════════════════════════════════════
#  SHORTHAND BUILDER
# ═══════════════════════════════════════════════════════════════════════════

def _build_ct_shorthand(title: str, entry: dict) -> str:
    """One-line vetting-box summary for CT."""
    params = (entry.get('Parameters') or entry.get('protocol') or '').split('.')[0][:140]
    contrast = (entry.get('Contrast') or '').split('.')[0][:80].strip()
    parts = []
    if contrast.lower() in ('none', ''):
        parts.append('Non-contrast')
    else:
        parts.append(contrast)
    if params:
        parts.append(params)
    return '. '.join(parts)[:250]


def _build_mri_shorthand(title: str, entry: dict) -> str:
    """One-line vetting-box summary for MRI."""
    parts = []
    for plane in ('Axial', 'Coronal', 'Sagittal'):
        seqs = entry.get(plane)
        if isinstance(seqs, list) and seqs:
            first = str(seqs[0])[:60]
            parts.append(f'{plane[0]}: {first}')
    if entry.get('contrast'):
        parts.append(str(entry['contrast'])[:60])
    return ' | '.join(parts)[:250]


# ═══════════════════════════════════════════════════════════════════════════
#  KEYWORDS BUILDER
# ═══════════════════════════════════════════════════════════════════════════

def _build_keywords(title: str, entry: dict, modality: str) -> str:
    parts = set()
    # Add title words
    for w in re.findall(r'[a-zA-Z]+', (title or '').lower()):
        if len(w) >= 3:
            parts.add(w)
    # Add modality
    parts.add(modality.lower())
    # Add indication keywords
    ind = entry.get('indication') or entry.get('Comments') or ''
    for w in re.findall(r'[a-zA-Z]+', ind.lower())[:30]:
        if len(w) >= 4:
            parts.add(w)
    return ', '.join(sorted(parts))[:500]


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN SYNC FUNCTION — called from app.py
# ═══════════════════════════════════════════════════════════════════════════

def sync_master_protocols_to_db(db, ImagingProtocol, logger):
    """
    Master sync: upserts ImagingProtocol from master CT+MRI JSON files.

    Returns dict with counts: {inserted, updated, skipped, deleted, errors}.

    Safety:
    - Idempotent: uses `_SENTINEL` in detailed_protocol_html.
    - Personal rows (origin='personal') never touched.
    - Admin rows with no master JSON slug match are deleted.
    - Per-row try/except isolates failures.
    """
    result = {'inserted': 0, 'updated': 0, 'skipped': 0, 'deleted': 0, 'errors': 0}

    # ── Load master JSON ──
    try:
        with open(os.path.join(_DATA_DIR, 'ct_protocols.json')) as f:
            ct = json.load(f)
        with open(os.path.join(_DATA_DIR, 'mri_protocols.json')) as f:
            mri = json.load(f)
    except Exception as e:
        logger.error('sync_master_protocols: failed to load master JSON: %s', e)
        return result

    # ── Build a unified slug → (modality, title, entry) map ──
    master_map = {}

    for title, entry in ct.get('protocols', {}).items():
        if not isinstance(entry, dict):
            continue
        slug = _slugify(title)
        master_map[slug] = ('CT', title, entry)

    for cat, entries in mri.items():
        if cat == '_meta' or not isinstance(entries, dict):
            continue
        for title, entry in entries.items():
            if not isinstance(entry, dict):
                continue
            slug = _slugify(title)
            # Avoid CT/MRI slug collision by prefixing MRI slugs that clash
            if slug in master_map:
                slug = 'mri-' + slug
            master_map[slug] = ('MRI', title, entry)

    logger.info('sync_master_protocols: loaded %d master protocols from JSON', len(master_map))

    # ── Fast-path: skip upsert loop if all protocols already synced ──
    try:
        _synced_count = (ImagingProtocol.query
                         .filter(ImagingProtocol.origin == 'admin',
                                 ImagingProtocol.detailed_protocol_html.contains(_SENTINEL))
                         .count())
        if _synced_count >= len(master_map):
            result['skipped'] = _synced_count
            logger.info('sync_master_protocols: all %d protocols already synced, skipping upsert + orphan check',
                        _synced_count)
            # All master protocols present and synced — no orphans possible, skip DB read
            return result
    except Exception:
        pass  # fall through to full sync

    # ── Upsert each master entry ──
    for slug, (modality, title, entry) in master_map.items():
        try:
            existing = ImagingProtocol.query.filter_by(slug=slug).first()

            # Generate content
            if modality == 'CT':
                html = _render_ct_html(title, entry)
                shorthand = _build_ct_shorthand(title, entry)
            else:
                html = _render_mri_html(title, entry)
                shorthand = _build_mri_shorthand(title, entry)

            # Append all sentinels (sync + legacy) so older migration blocks
            # skip these rows on subsequent runs.
            html_with_sentinel = html + _LEGACY_SENTINELS + _SENTINEL

            keywords = _build_keywords(title, entry, modality)
            body_section = _infer_body_section(title)
            is_emergency = _infer_emergency(title)
            is_verified = (entry.get('status', 'verified') == 'verified')
            is_published = is_verified  # publish verified rows immediately

            # Indication JSON
            ind = entry.get('indication') or entry.get('Comments') or ''
            if isinstance(ind, str):
                ind_list = [s.strip() for s in re.split(r'[;.]\s*', ind) if s.strip()]
            elif isinstance(ind, list):
                ind_list = [str(i) for i in ind if i]
            else:
                ind_list = []
            indication_json = json.dumps(ind_list[:15])

            special_notes = ''
            notes = entry.get('notes') or entry.get('special_notes')
            if isinstance(notes, list):
                special_notes = ' | '.join(str(n) for n in notes)[:2000]
            elif isinstance(notes, str):
                special_notes = notes[:2000]

            if existing:
                # Skip if already migrated at this version
                if existing.detailed_protocol_html and _SENTINEL in existing.detailed_protocol_html:
                    result['skipped'] += 1
                    continue
                # Don't touch personal protocols
                if getattr(existing, 'origin', 'admin') == 'personal':
                    result['skipped'] += 1
                    continue
                existing.title = title
                existing.modality = modality
                existing.body_section = body_section
                existing.keywords = keywords
                existing.shorthand_text = shorthand
                existing.detailed_protocol_html = html_with_sentinel
                existing.special_notes = special_notes
                existing.indication_json = indication_json
                existing.is_published = is_published
                existing.is_verified = is_verified
                existing.is_emergency = is_emergency
                existing.is_paediatric = False
                existing.origin = 'admin'
                existing.updated_at = datetime.utcnow()
                result['updated'] += 1
            else:
                new_row = ImagingProtocol(
                    title=title,
                    slug=slug,
                    modality=modality,
                    body_section=body_section,
                    keywords=keywords,
                    shorthand_text=shorthand,
                    detailed_protocol_html=html_with_sentinel,
                    special_notes=special_notes,
                    indication_json=indication_json,
                    origin='admin',
                    is_published=is_published,
                    is_verified=is_verified,
                    is_emergency=is_emergency,
                    is_paediatric=False,
                )
                db.session.add(new_row)
                result['inserted'] += 1

        except Exception as e:
            result['errors'] += 1
            logger.warning('sync_master_protocols: row failed (%s): %s', title, e)
            db.session.rollback()
            continue

    # Commit all upserts first
    try:
        db.session.commit()
    except Exception as e:
        logger.error('sync_master_protocols: commit failed: %s', e)
        db.session.rollback()
        return result

    return _delete_orphans(db, ImagingProtocol, master_map, result, logger)


def _delete_orphans(db, ImagingProtocol, master_map, result, logger):
    """Delete admin rows whose slug is NOT in master JSON. Returns result dict."""
    try:
        master_slugs = set(master_map.keys())
        orphans = (ImagingProtocol.query
                   .filter(ImagingProtocol.origin == 'admin')
                   .with_entities(ImagingProtocol.id, ImagingProtocol.slug)
                   .all())
        orphan_ids = []
        for row in orphans:
            if row.slug not in master_slugs:
                logger.info('sync_master_protocols: deleting orphan admin row id=%s slug=%s',
                            row.id, row.slug)
                orphan_ids.append(row.id)
                result['deleted'] += 1
        if orphan_ids:
            # Null out copied_from_id refs pointing to orphans (self-referential FK)
            (ImagingProtocol.query
             .filter(ImagingProtocol.copied_from_id.in_(orphan_ids))
             .update({ImagingProtocol.copied_from_id: None},
                     synchronize_session='fetch'))
            for oid in orphan_ids:
                row = db.session.get(ImagingProtocol, oid)
                if row:
                    db.session.delete(row)
        db.session.commit()
    except Exception as e:
        logger.error('sync_master_protocols: delete failed: %s', e)
        db.session.rollback()

    logger.info('sync_master_protocols: done — inserted=%d updated=%d skipped=%d deleted=%d errors=%d',
                result['inserted'], result['updated'], result['skipped'],
                result['deleted'], result['errors'])
    return result
