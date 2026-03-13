"""
Shared test fixtures for RadInsights.
"""
import os
import pytest

# Force test configuration before any app imports
os.environ['DATABASE_URL'] = 'sqlite://'  # In-memory DB
os.environ['SECRET_KEY'] = 'test-secret-key-for-pytest'
os.environ['TESTING'] = '1'


@pytest.fixture(scope='session')
def app():
    """Create application for testing."""
    from app import app as flask_app
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False

    with flask_app.app_context():
        from models import db
        db.create_all()
        yield flask_app
        db.drop_all()


@pytest.fixture
def client(app):
    """Test client for making requests."""
    return app.test_client()


@pytest.fixture
def db_session(app):
    """Database session for direct DB access in tests."""
    from models import db
    with app.app_context():
        yield db.session
        db.session.rollback()


@pytest.fixture
def logged_in_client(app):
    """Test client with a logged-in approved student user."""
    from models import db, User, UserRole
    from werkzeug.security import generate_password_hash

    with app.app_context():
        # Clean up any leftover test user from a previous run
        existing = User.query.filter_by(email='testuser@example.com').first()
        if existing:
            db.session.delete(existing)
            db.session.commit()

        user = User(
            email='testuser@example.com',
            full_name='Test User',
            password_hash=generate_password_hash('password123'),
            role=UserRole.STUDENT,
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    client = app.test_client()
    # Login via the auth endpoint
    resp = client.post('/auth/login', json={
        'email': 'testuser@example.com',
        'password': 'password123',
    })
    assert resp.status_code == 200, f'Login failed: {resp.get_json()}'

    yield client

    # Logout before deleting the user to avoid stale user references in Flask-Login
    client.post('/auth/logout')

    # Cleanup
    with app.app_context():
        u = User.query.get(user_id)
        if u:
            db.session.delete(u)
            db.session.commit()


@pytest.fixture
def admin_client(app):
    """Test client with a logged-in admin user."""
    from models import db, User, UserRole
    from werkzeug.security import generate_password_hash

    with app.app_context():
        existing = User.query.filter_by(email='admin@example.com').first()
        if existing:
            db.session.delete(existing)
            db.session.commit()

        user = User(
            email='admin@example.com',
            full_name='Admin User',
            password_hash=generate_password_hash('adminpass123'),
            role=UserRole.ADMIN,
            is_admin=True,
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    client = app.test_client()
    resp = client.post('/auth/login', json={
        'email': 'admin@example.com',
        'password': 'adminpass123',
    })
    assert resp.status_code == 200, f'Admin login failed: {resp.get_json()}'

    yield client

    # Logout before deleting the user to avoid stale user references in Flask-Login
    client.post('/auth/logout')

    with app.app_context():
        u = User.query.get(user_id)
        if u:
            db.session.delete(u)
            db.session.commit()
