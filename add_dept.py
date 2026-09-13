import csv
import os

fp = r'data\employee_history.csv'
deps = {
    'EMP001': 'Sales',
    'EMP002': 'Engineering',
    'EMP003': 'Sales',
    'EMP004': 'Marketing',
    'EMP005': 'Engineering'
}

rows = []
with open(fp, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    if 'department' not in fieldnames:
        fieldnames = fieldnames + ['department']
    for r in reader:
        r['department'] = deps.get(r['employee_id'], 'Sales')
        rows.append(r)

with open(fp, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print('Done')
