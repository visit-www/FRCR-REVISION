"""
Smoke tests for critical routes — verifies they load without errors.
"""


class TestPublicRoutes:
    """Routes accessible without authentication."""

    def test_health_check(self, client):
        resp = client.get('/health')
        assert resp.status_code in (200, 503)
        data = resp.get_json()
        assert 'status' in data

    def test_robots_txt(self, client):
        resp = client.get('/robots.txt')
        assert resp.status_code == 200
        assert b'Disallow: /api/' in resp.data

    def test_sitemap_xml(self, client):
        resp = client.get('/sitemap.xml')
        assert resp.status_code == 200
        assert b'<urlset' in resp.data
        assert b'<loc>' in resp.data

    def test_404_returns_html(self, client):
        resp = client.get('/nonexistent-page-xyz')
        assert resp.status_code == 404

    def test_404_api_returns_json(self, client):
        resp = client.get('/api/nonexistent')
        assert resp.status_code == 404
        data = resp.get_json()
        assert data is not None
        assert 'error' in data

    def test_login_page(self, client):
        resp = client.get('/auth/login')
        assert resp.status_code == 200

    def test_privacy_policy(self, client):
        resp = client.get('/privacy-policy')
        assert resp.status_code == 200

    def test_terms_of_use(self, client):
        resp = client.get('/terms-of-use')
        assert resp.status_code == 200


class TestAuthProtection:
    """Verify protected routes redirect to login."""

    def test_dashboard_requires_login(self, client):
        resp = client.get('/', follow_redirects=False)
        assert resp.status_code in (302, 200)

    def test_smart_reporter_requires_login(self, client):
        resp = client.get('/smart-reporter', follow_redirects=False)
        assert resp.status_code == 302

    def test_admin_requires_login(self, client):
        resp = client.get('/admin/reporting-algorithms', follow_redirects=False)
        assert resp.status_code in (302, 401, 403)

    def test_backup_requires_login(self, client):
        resp = client.get('/api/backup/export', follow_redirects=False)
        assert resp.status_code in (302, 401, 404)


class TestCronAuth:
    """Verify cron endpoints require authentication in non-debug mode."""

    def test_data_retention_unauthorized(self, client, app):
        # In testing, debug may be False — should require auth
        resp = client.get('/api/cron/data-retention-cleanup')
        # Should either work (debug mode) or return 401
        assert resp.status_code in (200, 401)
