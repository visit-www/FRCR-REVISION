#!/usr/bin/env python3
"""Fix all indentation errors in app.py"""

with open('app.py', 'r') as f:
    lines = f.readlines()

# Fix line 570 (index 569) - db.create_all() should be indented inside except block
if len(lines) > 569 and 'db.create_all()' in lines[569]:
    lines[569] = '            db.create_all()\n'

# Fix line 571 (index 570) - print should be indented inside except block  
if len(lines) > 570 and 'Database schema created successfully' in lines[570]:
    lines[570] = '            print("[DB] Database schema created successfully")\n'

# Fix line 793 (index 792) - return should be indented
if len(lines) > 792 and 'return redirect(url_for("view_revision_case"' in lines[792]:
    lines[792] = '        return redirect(url_for("view_revision_case", session_id=revision_session.id, case_index=0))\n'

# Fix line 952 (index 951) - query should be indented inside if block
if len(lines) > 951 and 'query = Case.query.filter_by(module=module_enum, is_public=True)' in lines[951]:
    lines[951] = '        query = Case.query.filter_by(module=module_enum, is_public=True)\n'

# Fix line 1000 (index 999) - has_notes should be indented inside for loop
if len(lines) > 999 and 'has_notes = CandidateNote.query' in lines[999]:
    lines[999] = '            has_notes = CandidateNote.query.filter_by(case_id=case.id, user_id=current_user.id).first() is not None\n'

# Fix line 1001 (index 1000) - cases_data.append should be indented inside for loop
if len(lines) > 1000 and 'cases_data.append({' in lines[1000]:
    lines[1000] = '            cases_data.append({\n'

# Fix line 1028 (index 1027) - return should be indented inside else block
if len(lines) > 1027 and 'return render_template(\'cases_list.html\'' in lines[1027]:
    lines[1027] = '        return render_template(\'cases_list.html\',\n'

# Fix line 1913 (index 1912) - if should be indented inside try block
if len(lines) > 1912 and 'if not case:' in lines[1912]:
    lines[1912] = '        if not case:\n'

with open('app.py', 'w') as f:
    f.writelines(lines)

print("✓ Fixed all indentation errors in app.py")
