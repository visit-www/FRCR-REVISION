"""Seed Head and Neck display_order (product-owner order)

Revision ID: seed_head_neck_display_order
Revises: add_display_order_ajcc_site
Create Date: 2026-01-30

Sets display_order for Head and Neck disease sites by slug so the section
page shows the intended order (Staging Principles first, then Cervical Lymph
Nodes, Nasopharynx, etc.). Idempotent: safe to run multiple times.
"""
from alembic import op
from sqlalchemy import text


revision = 'seed_head_neck_display_order'
down_revision = 'add_display_order_ajcc_site'
branch_labels = None
depends_on = None


# Product-owner order for Head and Neck (slug -> display_order 1..11)
HEAD_NECK_ORDER = [
    ('staging-head-and-neck-cancers', 1),
    ('cervical-lymph-nodes-and-unknown-primary-tumors-of-the-head-and-neck', 2),
    ('nasopharynx', 3),
    ('oropharynx-hpv-associated', 4),
    ('oropharynx-hpv-independent-and-hypopharynx', 5),
    ('oral-cavity', 6),
    ('larynx', 7),
    ('nasal-cavity-and-paranasal-sinuses', 8),
    ('salivary-glands', 9),
    ('cutaneous-carcinoma-of-the-head-and-neck', 10),
    ('mucosal-melanoma-of-the-head-and-neck', 11),
]


def upgrade():
    conn = op.get_bind()
    r = conn.execute(text(
        "SELECT id FROM ajcc_body_section WHERE slug = 'head-and-neck'"
    )).fetchone()
    if not r:
        return
    section_id = r[0]
    for slug, order_val in HEAD_NECK_ORDER:
        conn.execute(
            text(
                "UPDATE ajcc_disease_site SET display_order = :ord "
                "WHERE body_section_id = :section_id AND slug = :slug"
            ),
            {"ord": order_val, "section_id": section_id, "slug": slug},
        )


def downgrade():
    # Reset Head and Neck display_order to 0 (optional)
    conn = op.get_bind()
    conn.execute(
        text(
            "UPDATE ajcc_disease_site SET display_order = 0 "
            "WHERE body_section_id = (SELECT id FROM ajcc_body_section WHERE slug = 'head-and-neck')"
        )
    )
