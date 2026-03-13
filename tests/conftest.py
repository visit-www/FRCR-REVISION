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
