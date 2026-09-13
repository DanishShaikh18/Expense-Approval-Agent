import re

with open('data/seed_db.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'\s*"image_hash"\s*:\s*".*?",', '', content)

with open('data/seed_db.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("done")
