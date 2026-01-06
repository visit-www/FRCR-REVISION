# Changelog

All notable changes to FRCR Examiner Tool will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-01-06

### Added
- **Core Features**
  - Complete exam session management system
  - Candidate registration and management
  - Medical case organization with packets
  - Image upload and management for cases
  - Q&A pair creation and management
  - Exam workflow for conducting viva exams
  - Admin dashboard with system controls

- **Technical Features**
  - Flask web framework with SQLAlchemy ORM
  - Bootstrap 5 responsive UI
  - RESTful API endpoints
  - Automatic database backups
  - Session-based user management
  - Error handling and validation

- **Database**
  - SQLite support for development
  - PostgreSQL support for production
  - Automatic schema generation
  - Data relationship management

- **Frontend**
  - Responsive Bootstrap 5 design
  - Intuitive navigation system
  - Modal dialogs for forms
  - Image gallery viewer
  - Real-time form validation

- **Documentation**
  - Comprehensive README.md
  - User guide (HOW_TO_USE.md)
  - Setup and installation guide (SETUP.md)
  - Contributing guidelines (CONTRIBUTING.md)
  - This changelog

### Features
- ✅ Exam session creation and management
- ✅ Candidate registration with unique identifiers
- ✅ Packet organization for exam cases
- ✅ Medical case management with descriptions
- ✅ Image upload and annotation
- ✅ Q&A pair creation for case discussion
- ✅ Complete exam workflow
- ✅ Automatic backups
- ✅ Admin panel
- ✅ Responsive design

### Technical Stack
- Python 3.7+
- Flask web framework
- SQLAlchemy ORM
- Bootstrap 5
- PostgreSQL/SQLite
- Vanilla JavaScript

---

## Future Releases

### [Planned 1.1.0]
- [ ] User authentication and roles
- [ ] Candidate evaluation scoring
- [ ] Exam results reporting
- [ ] Video case support
- [ ] Case templates and cloning
- [ ] Bulk candidate import (CSV)
- [ ] Exam statistics and analytics
- [ ] Email notifications
- [ ] Dark mode interface

### [Planned 1.2.0]
- [ ] Mobile app (iOS/Android)
- [ ] Real-time collaboration features
- [ ] Advanced search and filtering
- [ ] Custom exam templates
- [ ] Integration with medical databases
- [ ] Audio recording of sessions
- [ ] Exam scheduling system
- [ ] Candidate feedback forms

### [Planned 2.0.0]
- [ ] Machine learning for candidate evaluation
- [ ] Automated image analysis
- [ ] Multi-language support
- [ ] Advanced reporting and analytics
- [ ] API key authentication
- [ ] Webhook integration
- [ ] Cloud storage integration
- [ ] Progressive Web App (PWA)

---

## Known Issues

### Current Version (1.0.0)
- Session dates cannot be edited after creation (workaround: create new session)
- Large image uploads may take time (recommended < 5MB per image)
- Bulk operations are not yet supported

---

## Migration Guide

### From Previous Versions
None - this is the initial release.

---

## Performance Notes

### Version 1.0.0
- Optimized for sessions with up to 100 candidates
- Recommended maximum 1000 cases per session
- Database backups occur every 24 hours automatically
- Image storage: Files stored locally in instance directory

---

## Security

### Version 1.0.0
- CSRF protection enabled for all forms
- SQL injection protection via SQLAlchemy ORM
- File upload validation
- Input sanitization on forms
- Session-based authentication support
- Database encryption recommended for production

### Recommended Security Practices
- Use HTTPS in production
- Set strong SECRET_KEY
- Use PostgreSQL in production
- Enable automatic backups
- Regular security updates
- User role management

---

## Contributors

### Version 1.0.0
- **Author**: Dr Gaurav S.P Gupta, MBBS, MD, FRCR
- **Email**: lotusheart2016@gmail.com

---

## Support

- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Email**: lotusheart2016@gmail.com

---

## Versioning

This project follows [Semantic Versioning](https://semver.org/):
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes

---

## License

Educational and professional use for medical training environments.

---

## Acknowledgments

- Bootstrap team for UI framework
- Flask team for web framework
- SQLAlchemy team for ORM
- Medical education community for feedback

---

**Note**: This changelog is continuously updated. Check back for new releases and updates.

Last Updated: 2026-01-06
