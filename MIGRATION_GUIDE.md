# Alembic Migration Guide for FRCR Revision

## ✅ Setup Complete!

Your project now uses **Flask-Migrate** (which wraps Alembic) for database migrations.

---

## 📁 What Was Created?

- `/migrations/` - Migration scripts directory
- `/migrations/versions/` - Individual migration files
- `.flaskenv` - Flask environment configuration

---

## 🚀 Common Commands

### 1. **Create a New Migration** (after changing models)
```bash
flask db migrate -m "Description of changes"
```
This auto-generates a migration script by comparing your models to the database.

### 2. **Apply Migrations** (upgrade database)
```bash
flask db upgrade
```
Applies all pending migrations to bring database up-to-date.

### 3. **Rollback Last Migration**
```bash
flask db downgrade
```
Reverts the most recent migration.

### 4. **View Migration History**
```bash
flask db history
```
Shows all migrations and their status.

### 5. **Check Current Version**
```bash
flask db current
```
Shows which migration your database is at.

---

## 📝 Workflow Example

### Scenario: Adding a new field to User model

1. **Edit models.py**:
```python
class User(UserMixin, db.Model):
    # ... existing fields ...
    phone_number = db.Column(db.String(20), nullable=True)  # NEW FIELD
```

2. **Generate migration**:
```bash
flask db migrate -m "Add phone number to User"
```

3. **Review the generated file** in `migrations/versions/`:
```python
def upgrade():
    op.add_column('user', sa.Column('phone_number', sa.String(20), nullable=True))

def downgrade():
    op.drop_column('user', 'phone_number')
```

4. **Apply migration**:
```bash
flask db upgrade
```

---

## 🔍 Current Status

Your database is now tracked at migration:
- **Version**: `0c00cb7b7f78`
- **Description**: "Initial migration with all models"

This migration captures:
- ✅ User model with `is_admin` column
- ✅ Case model with `module`, `body_part`, `is_public`
- ✅ CandidateNote model
- ✅ TextHighlight model
- ✅ All existing tables

---

## ⚠️ Important Notes

1. **Always commit migration files to Git** - Your team needs them!
2. **Review auto-generated migrations** - Sometimes Alembic needs help with complex changes
3. **Never edit applied migrations** - Create a new migration instead
4. **Backup before major migrations** - Especially in production

---

## 🆚 vs. migrate_database.py

| Feature | migrate_database.py | Alembic (Flask-Migrate) |
|---------|-------------------|------------------------|
| Version control | ❌ No | ✅ Yes |
| Auto-generate | ❌ Manual SQL | ✅ From models |
| Rollback support | ❌ No | ✅ Yes |
| Team collaboration | ❌ Hard | ✅ Easy |
| Production ready | ⚠️ One-time fix | ✅ Industry standard |

**You can delete `migrate_database.py` now** - You won't need it anymore!

---

## 🚢 Production Deployment

When deploying to Vercel/production:

1. **Push migrations to Git**:
```bash
git add migrations/
git commit -m "Add database migrations"
```

2. **In production, run**:
```bash
flask db upgrade
```

This will apply all migrations to your production PostgreSQL database.

---

## 🐛 Troubleshooting

### "Target database is not up to date"
```bash
flask db stamp head  # Mark current state
```

### "Migration failed"
```bash
flask db downgrade   # Rollback
# Fix the issue
flask db upgrade     # Try again
```

### "Circular dependency detected"
Review the migration file and adjust dependencies manually.

---

## 📚 Learn More

- [Flask-Migrate Docs](https://flask-migrate.readthedocs.io/)
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
