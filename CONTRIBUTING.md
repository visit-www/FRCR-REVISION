# Contributing to FRCR Examiner Tool

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

- Be respectful and professional
- Help others learn and grow
- Provide constructive feedback
- Respect medical standards and regulations

## Getting Started

### Prerequisites
- Python 3.7+
- Git
- Virtual environment experience
- Basic Flask knowledge

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/visit-www/Frcr-examiner.git
cd Frcr-examiner

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run in development mode
export FLASK_ENV=development
flask run
```

## Development Workflow

### 1. Create a Feature Branch
```bash
git checkout -b feature/your-feature-name
# or for bug fixes
git checkout -b fix/bug-description
```

### 2. Make Your Changes
- Follow PEP 8 style guide for Python code
- Write clear, self-documenting code
- Add comments for complex logic
- Keep functions small and focused

### 3. Test Your Changes
- Test locally on `http://localhost:5000`
- Test with sample data
- Verify no existing features are broken
- Test on different screen sizes

### 4. Commit Your Changes
```bash
git add .
git commit -m "descriptive: explain what you changed"
```

Use clear commit messages:
- `feat:` for new features
- `fix:` for bug fixes
- `refactor:` for code improvements
- `docs:` for documentation
- `style:` for formatting/styling
- `test:` for test additions

### 5. Push and Create Pull Request
```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub with:
- Clear title
- Description of changes
- Why the change is needed
- Any related issues

## Code Style Guidelines

### Python Code
- Follow PEP 8
- Use meaningful variable names
- Keep functions under 50 lines when possible
- Document complex functions with docstrings

Example:
```python
def create_exam_session(name, exam_date, exam_time):
    """
    Create a new exam session.
    
    Args:
        name (str): Session name
        exam_date (str): Exam date (YYYY-MM-DD)
        exam_time (str): Exam time (HH:MM)
    
    Returns:
        Session: The created session object
    """
    session = ExamSession(
        session_name=name,
        exam_date=exam_date,
        exam_time=exam_time
    )
    db.session.add(session)
    db.session.commit()
    return session
```

### JavaScript Code
- Use clear variable names
- Keep functions small
- Use comments for complex logic
- Avoid global variables

### HTML/CSS
- Use Bootstrap 5 classes
- Maintain consistent indentation
- Use semantic HTML
- Keep styles in CSS files, not inline

## Database Changes

### Adding a New Model
1. Define the model in `models.py`
2. Add necessary relationships
3. Create migration if needed
4. Test with sample data

Example:
```python
class NewModel(db.Model):
    __tablename__ = 'new_table'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<NewModel {self.name}>'
```

### Modifying Existing Models
- Add new columns with default values
- Keep backward compatibility
- Document schema changes

## API Endpoint Changes

### Adding New Endpoints
1. Add route in `app.py`
2. Include proper error handling
3. Return JSON responses
4. Document the endpoint
5. Test with curl or Postman

Example:
```python
@app.route('/api/resource/<int:resource_id>', methods=['GET'])
def get_resource(resource_id):
    """Get resource by ID"""
    resource = Resource.query.get_or_404(resource_id)
    return jsonify({
        'id': resource.id,
        'name': resource.name
    })
```

### API Response Format
Always use consistent JSON structure:
```json
{
    "status": "success",
    "data": {},
    "message": "Success message"
}
```

For errors:
```json
{
    "status": "error",
    "message": "Error description"
}
```

## Frontend Changes

### Templates
- Use Bootstrap 5 components
- Keep templates clean
- Use Jinja2 efficiently
- Maintain responsive design

### JavaScript
- Avoid jQuery (use vanilla JavaScript)
- Use fetch API for AJAX
- Handle errors gracefully
- Show user feedback

Example:
```javascript
function saveData(data) {
    fetch('/api/endpoint', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'success') {
            alert('Success!');
            location.reload();
        } else {
            alert('Error: ' + data.message);
        }
    })
    .catch(e => alert('Network error: ' + e.message));
}
```

## Testing

### Manual Testing
- Test with sample data
- Test edge cases
- Test error scenarios
- Test on different browsers

### Areas to Test When Contributing
- User interface responsiveness
- Form validation
- Database operations
- API responses
- Error handling

## Documentation

### Update Documentation When
- Adding new features
- Changing user workflows
- Adding API endpoints
- Modifying database schema
- Changing configuration

### Files to Update
- `README.md` - For technical changes
- `HOW_TO_USE.md` - For user-facing changes
- Code comments - For complex logic

## Common Issues & Solutions

### Issue: Database locked
**Solution**: Restart Flask, ensure only one instance is running

### Issue: JavaScript not loading
**Solution**: Clear browser cache, verify static files exist

### Issue: Images not uploading
**Solution**: Check file permissions, verify upload directory exists

### Issue: Port 5000 in use
**Solution**: Use `flask run --port 5001` or kill the process

## Performance Considerations

- Minimize database queries
- Cache frequently accessed data
- Optimize image file sizes
- Use lazy loading for large lists
- Consider pagination for large datasets

## Security Guidelines

- Never commit sensitive data
- Use environment variables for secrets
- Validate all user inputs
- Use CSRF protection for forms
- Sanitize file uploads
- Hash passwords if applicable

## Deployment Considerations

- Test on staging environment first
- Document any new dependencies
- Verify database migrations work
- Check backup functionality
- Test on production-like environment

## Review Process

### Before Submitting PR
- [ ] Code follows style guidelines
- [ ] All tests pass
- [ ] Documentation updated
- [ ] No breaking changes
- [ ] Commit messages are clear

### PR Review Checklist
- [ ] Code quality
- [ ] Functionality works as intended
- [ ] No security issues
- [ ] Documentation is clear
- [ ] Tests cover new code

## Questions?

- Check existing issues/PRs
- Review documentation
- Contact: lotusheart2016@gmail.com

## Thank You! 🙏

Your contributions help make FRCR Examiner Tool better for everyone. Thank you for being part of the community!
