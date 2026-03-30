"""
Integration tests for RadInsights Flask app.

Covers: auth flows, case CRUD, admin operations, content requests.

NOTE: The app fixture is session-scoped, so Flask-Login state (via flask.g)
can leak between test clients within the same app context. Tests that log in
must also log out within the same client block, and tests that need a clean
unauthenticated state use `flask_login.logout_user()` as a guard.
"""
import pytest


# ==================== AUTH FLOWS ====================

class TestRegistration:
    """User registration flow."""

    def test_register_new_user(self, app):
        """Registering a new user returns 201 and success JSON."""
        from models import db, User

        with app.test_client() as c:
            resp = c.post('/auth/register', json={
                'email': 'newuser@example.com',
                'password': 'securepass99',
                'full_name': 'New User',
            })
            assert resp.status_code == 201
            data = resp.get_json()
            assert data['success'] is True
            # Registration auto-logs in — log out to avoid leaking state
            c.post('/auth/logout')

        # Cleanup
        with app.app_context():
            u = User.query.filter_by(email='newuser@example.com').first()
            if u:
                db.session.delete(u)
                db.session.commit()

    def test_register_duplicate_email(self, app):
        """Registering with an existing email returns 409."""
        from models import db, User
        from werkzeug.security import generate_password_hash

        with app.app_context():
            existing = User.query.filter_by(email='dupe@example.com').first()
            if not existing:
                u = User(
                    email='dupe@example.com',
                    full_name='Dupe User',
                    password_hash=generate_password_hash('password123'),
                )
                db.session.add(u)
                db.session.commit()

        with app.test_client() as c:
            resp = c.post('/auth/register', json={
                'email': 'dupe@example.com',
                'password': 'anotherpass1',
                'full_name': 'Another User',
            })
            assert resp.status_code == 409
            data = resp.get_json()
            assert 'already registered' in data['error'].lower()

        # Cleanup
        with app.app_context():
            u = User.query.filter_by(email='dupe@example.com').first()
            if u:
                db.session.delete(u)
                db.session.commit()

    def test_register_short_password(self, app):
        """Password shorter than 8 characters returns 400."""
        with app.test_client() as c:
            resp = c.post('/auth/register', json={
                'email': 'short@example.com',
                'password': 'short',
                'full_name': 'Short Pass',
            })
            assert resp.status_code == 400
            assert 'at least 8' in resp.get_json()['error'].lower()

    def test_register_missing_fields(self, app):
        """Missing required fields returns 400."""
        with app.test_client() as c:
            resp = c.post('/auth/register', json={
                'email': 'nopass@example.com',
                'password': '',
                'full_name': '',
            })
            assert resp.status_code == 400


class TestLogin:
    """User login flow."""

    def test_login_success(self, app):
        """Valid credentials return 200 with success JSON."""
        from models import db, User, UserRole
        from werkzeug.security import generate_password_hash

        with app.app_context():
            existing = User.query.filter_by(email='logintest@example.com').first()
            if existing:
                db.session.delete(existing)
                db.session.commit()
            u = User(
                email='logintest@example.com',
                full_name='Login Test',
                password_hash=generate_password_hash('password123'),
                role=UserRole.STUDENT,
                is_active=True,
            )
            db.session.add(u)
            db.session.commit()

        with app.test_client() as c:
            resp = c.post('/auth/login', json={
                'email': 'logintest@example.com',
                'password': 'password123',
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert data['success'] is True
            # Log out to avoid leaking auth state
            c.post('/auth/logout')

        # Cleanup
        with app.app_context():
            u = User.query.filter_by(email='logintest@example.com').first()
            if u:
                db.session.delete(u)
                db.session.commit()

    def test_login_wrong_password(self, app):
        """Wrong password returns 401."""
        from models import db, User, UserRole
        from werkzeug.security import generate_password_hash
        from flask_login import logout_user

        # Guard against leaked auth state from prior tests
        with app.app_context():
            try:
                logout_user()
            except Exception:
                pass

        with app.app_context():
            existing = User.query.filter_by(email='wrongpass@example.com').first()
            if existing:
                db.session.delete(existing)
                db.session.commit()
            u = User(
                email='wrongpass@example.com',
                full_name='Wrong Pass',
                password_hash=generate_password_hash('correctpass1'),
                role=UserRole.STUDENT,
                is_active=True,
            )
            db.session.add(u)
            db.session.commit()

        with app.test_client() as c:
            resp = c.post('/auth/login', json={
                'email': 'wrongpass@example.com',
                'password': 'wrongpassword',
            })
            assert resp.status_code == 401

        # Cleanup
        with app.app_context():
            u = User.query.filter_by(email='wrongpass@example.com').first()
            if u:
                db.session.delete(u)
                db.session.commit()

    def test_login_nonexistent_user(self, app):
        """Login with unknown email returns 401."""
        from flask_login import logout_user

        with app.app_context():
            try:
                logout_user()
            except Exception:
                pass

        with app.test_client() as c:
            resp = c.post('/auth/login', json={
                'email': 'nobody@example.com',
                'password': 'whatever123',
            })
            assert resp.status_code == 401

    def test_login_disabled_account(self, app):
        """Login with is_active=False returns 403."""
        from models import db, User, UserRole
        from werkzeug.security import generate_password_hash
        from flask_login import logout_user

        with app.app_context():
            try:
                logout_user()
            except Exception:
                pass

        with app.app_context():
            existing = User.query.filter_by(email='disabled@example.com').first()
            if existing:
                db.session.delete(existing)
                db.session.commit()
            u = User(
                email='disabled@example.com',
                full_name='Disabled User',
                password_hash=generate_password_hash('password123'),
                role=UserRole.STUDENT,
                is_active=False,
            )
            db.session.add(u)
            db.session.commit()

        with app.test_client() as c:
            resp = c.post('/auth/login', json={
                'email': 'disabled@example.com',
                'password': 'password123',
            })
            assert resp.status_code == 403

        # Cleanup
        with app.app_context():
            u = User.query.filter_by(email='disabled@example.com').first()
            if u:
                db.session.delete(u)
                db.session.commit()


class TestLogout:
    """Logout flow."""

    def test_logout(self, logged_in_client):
        """Logged-in user can log out successfully."""
        resp = logged_in_client.post('/auth/logout')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_logout_requires_login(self, app):
        """Unauthenticated logout returns redirect or 401."""
        from flask_login import logout_user

        with app.app_context():
            try:
                logout_user()
            except Exception:
                pass

        with app.test_client() as c:
            resp = c.post('/auth/logout', follow_redirects=False)
            assert resp.status_code in (302, 401)


class TestLoginLockout:
    """Brute force protection -- account lockout after failed attempts."""

    def test_lockout_after_max_failures(self, app):
        """After 5 failed logins the account is locked (429)."""
        from models import db, User, UserRole
        from werkzeug.security import generate_password_hash
        from flask_login import logout_user

        with app.app_context():
            try:
                logout_user()
            except Exception:
                pass

        with app.app_context():
            existing = User.query.filter_by(email='lockout@example.com').first()
            if existing:
                db.session.delete(existing)
                db.session.commit()
            u = User(
                email='lockout@example.com',
                full_name='Lockout User',
                password_hash=generate_password_hash('realpass123'),
                role=UserRole.STUDENT,
                is_active=True,
            )
            db.session.add(u)
            db.session.commit()

        # Clear rate limit entries so DB-backed limiter doesn't interfere with lockout test
        with app.app_context():
            from models import RateLimitEntry
            RateLimitEntry.query.filter_by(endpoint='auth.login').delete()
            db.session.commit()

        with app.test_client() as c:
            # Exceed the MAX_FAILED_LOGINS threshold (5)
            for _ in range(5):
                c.post('/auth/login', json={
                    'email': 'lockout@example.com',
                    'password': 'wrongpassword',
                })

            # The 6th attempt should be locked
            resp = c.post('/auth/login', json={
                'email': 'lockout@example.com',
                'password': 'wrongpassword',
            })
            assert resp.status_code == 429
            assert 'locked' in resp.get_json()['error'].lower() or 'too many' in resp.get_json()['error'].lower()

        # Cleanup
        with app.app_context():
            u = User.query.filter_by(email='lockout@example.com').first()
            if u:
                db.session.delete(u)
                db.session.commit()


# ==================== CASE CRUD ====================

class TestCaseCRUD:
    """Case create, read, edit, delete via admin."""

    def test_create_case(self, app, admin_client):
        """Admin can create a case via /api/case/create."""
        resp = admin_client.post('/api/case/create', json={
            'diagnosis': 'Integration Test Diagnosis',
            'module': 'CARDIOTHORACIC_VASCULAR',
            'body_part': 'LUNG_MEDIASTINUM',
            'pairs': [
                {
                    'question_text': 'What are the findings?',
                    'answer_text': 'Mass in the right upper lobe.',
                }
            ],
        })
        assert resp.status_code in (200, 201), f'Create case failed: {resp.get_json()}'
        data = resp.get_json()
        assert data.get('success') is True or data.get('case_id') is not None

        case_id = data.get('case_id') or data.get('id')
        assert case_id is not None

        # Cleanup
        from models import db, Case
        with app.app_context():
            c = Case.query.get(case_id)
            if c:
                db.session.delete(c)
                db.session.commit()

    def test_view_case(self, app, admin_client):
        """Admin can view a case via /view-case/<id>."""
        from models import db, Case, FRCRModule, BodyPart

        with app.app_context():
            case = Case(
                diagnosis='View Test Case',
                module=FRCRModule.CARDIOTHORACIC_VASCULAR,
                body_part=BodyPart.LUNG_MEDIASTINUM,
            )
            db.session.add(case)
            db.session.commit()
            case_id = case.id

        resp = admin_client.get(f'/view-case/{case_id}')
        assert resp.status_code == 200

        # Cleanup
        with app.app_context():
            c = Case.query.get(case_id)
            if c:
                db.session.delete(c)
                db.session.commit()

    def test_edit_case(self, app, admin_client):
        """Admin can edit a case via PUT /api/case/<id>."""
        from models import db, Case, FRCRModule, BodyPart

        with app.app_context():
            case = Case(
                diagnosis='Edit Test Case',
                module=FRCRModule.CARDIOTHORACIC_VASCULAR,
                body_part=BodyPart.LUNG_MEDIASTINUM,
            )
            db.session.add(case)
            db.session.commit()
            case_id = case.id

        resp = admin_client.put(f'/api/case/{case_id}', json={
            'diagnosis': 'Edited Diagnosis',
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('success') is True

        # Verify edit took effect
        with app.app_context():
            c = Case.query.get(case_id)
            assert c.diagnosis == 'Edited Diagnosis'

        # Cleanup
        with app.app_context():
            c = Case.query.get(case_id)
            if c:
                db.session.delete(c)
                db.session.commit()

    def test_delete_case(self, app, admin_client):
        """Admin can delete a case via DELETE /api/admin/cases/<id>."""
        from models import db, Case, FRCRModule, BodyPart

        with app.app_context():
            case = Case(
                diagnosis='Delete Test Case',
                module=FRCRModule.CARDIOTHORACIC_VASCULAR,
                body_part=BodyPart.LUNG_MEDIASTINUM,
            )
            db.session.add(case)
            db.session.commit()
            case_id = case.id

        resp = admin_client.delete(f'/api/admin/cases/{case_id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('success') is True

        # Verify deletion
        with app.app_context():
            assert Case.query.get(case_id) is None

    def test_student_cannot_delete_case(self, app, logged_in_client):
        """Non-admin user cannot delete a case (403)."""
        from models import db, Case, FRCRModule, BodyPart

        with app.app_context():
            case = Case(
                diagnosis='No Delete Case',
                module=FRCRModule.CARDIOTHORACIC_VASCULAR,
                body_part=BodyPart.LUNG_MEDIASTINUM,
            )
            db.session.add(case)
            db.session.commit()
            case_id = case.id

        resp = logged_in_client.delete(f'/api/admin/cases/{case_id}')
        assert resp.status_code in (401, 403)

        # Cleanup
        with app.app_context():
            c = Case.query.get(case_id)
            if c:
                db.session.delete(c)
                db.session.commit()


# ==================== ADMIN OPERATIONS ====================

class TestAdminAccess:
    """Admin-only route access control."""

    def test_admin_case_list(self, admin_client):
        """Admin can access /api/admin/cases."""
        resp = admin_client.get('/api/admin/cases')
        assert resp.status_code == 200

    def test_student_cannot_access_admin_cases(self, logged_in_client):
        """Student gets 401 or 403 on admin case list."""
        resp = logged_in_client.get('/api/admin/cases')
        assert resp.status_code in (401, 403)

    def test_unauthenticated_admin_access(self, app):
        """Unauthenticated request to admin route gets 401."""
        from flask_login import logout_user

        with app.app_context():
            try:
                logout_user()
            except Exception:
                pass

        with app.test_client() as c:
            resp = c.get('/api/admin/cases', follow_redirects=False)
            assert resp.status_code in (302, 401)

    def test_admin_reporting_algorithms_page(self, admin_client):
        """Admin can access the algorithms management page."""
        resp = admin_client.get('/admin/reporting-algorithms')
        assert resp.status_code == 200


class TestAlgorithmVerify:
    """Admin verify/unverify reporting algorithms."""

    def test_verify_algorithm(self, app, admin_client):
        """Admin can verify (publish) a reporting algorithm."""
        from models import db, ReportingAlgorithm

        with app.app_context():
            algo = ReportingAlgorithm(
                slug='test-verify-algo',
                title='Test Verify Algorithm',
                origin='admin',
                category='emergency',
                is_available=False,
            )
            db.session.add(algo)
            db.session.commit()
            algo_id = algo.id

        resp = admin_client.post(
            f'/admin/reporting-algorithms/api/{algo_id}/verify'
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('success') is True

        # Verify DB state
        with app.app_context():
            algo = ReportingAlgorithm.query.get(algo_id)
            assert algo.is_available is True
            assert algo.verified_by_user_id is not None

        # Cleanup
        with app.app_context():
            a = ReportingAlgorithm.query.get(algo_id)
            if a:
                db.session.delete(a)
                db.session.commit()

    def test_student_cannot_verify_algorithm(self, app, logged_in_client):
        """Non-admin cannot verify algorithms (401/403)."""
        from models import db, ReportingAlgorithm

        with app.app_context():
            algo = ReportingAlgorithm(
                slug='test-no-verify-algo',
                title='No Verify Algorithm',
                origin='admin',
                category='routine',
                is_available=False,
            )
            db.session.add(algo)
            db.session.commit()
            algo_id = algo.id

        resp = logged_in_client.post(
            f'/admin/reporting-algorithms/api/{algo_id}/verify'
        )
        assert resp.status_code in (401, 403)

        # Verify it was NOT published
        with app.app_context():
            algo = ReportingAlgorithm.query.get(algo_id)
            assert algo.is_available is False

        # Cleanup
        with app.app_context():
            a = ReportingAlgorithm.query.get(algo_id)
            if a:
                db.session.delete(a)
                db.session.commit()


# ==================== CONTENT REQUESTS ====================

class TestContentRequest:
    """Content request submission."""

    def test_submit_content_request(self, app, logged_in_client):
        """Logged-in user can submit a content request."""
        from models import db, ContentRequest

        resp = logged_in_client.post('/api/smart-reporter/content-request', json={
            'request_type': 'template',
            'title': 'CT Angiography of the Aorta',
            'description': 'Standard template for CTA aorta reporting.',
            'body_section': 'Thorax',
        })
        assert resp.status_code == 200, f'Content request failed: {resp.get_json()}'
        data = resp.get_json()
        assert data.get('success') is True

        # Cleanup
        with app.app_context():
            cr = ContentRequest.query.filter_by(title='CT Angiography of the Aorta').first()
            if cr:
                db.session.delete(cr)
                db.session.commit()

    def test_content_request_requires_login(self, app):
        """Unauthenticated content request is rejected."""
        from flask_login import logout_user

        with app.app_context():
            try:
                logout_user()
            except Exception:
                pass

        with app.test_client() as c:
            resp = c.post('/api/smart-reporter/content-request', json={
                'request_type': 'algorithm',
                'title': 'Some Algorithm',
                'description': 'Some description',
            }, follow_redirects=False)
            assert resp.status_code in (302, 401)

    def test_content_request_invalid_type(self, logged_in_client):
        """Invalid request_type returns 400."""
        resp = logged_in_client.post('/api/smart-reporter/content-request', json={
            'request_type': 'invalid_type',
            'title': 'Bad Type Request',
            'description': 'Testing bad type.',
        })
        assert resp.status_code == 400

    def test_content_request_missing_title(self, logged_in_client):
        """Missing title returns 400."""
        resp = logged_in_client.post('/api/smart-reporter/content-request', json={
            'request_type': 'template',
            'title': '',
            'description': 'No title provided.',
        })
        assert resp.status_code == 400
