import re

with open('test_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''r = client.post(f"/worlds/{WORLD}/seed-demo", json={"overwrite": True})'''
new = '''r = client.post(f"/worlds/{WORLD}/seed-demo?overwrite=true")'''

if old in content:
    content = content.replace(old, new)
    with open('test_engine.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Fixed successfully')
else:
    print('Pattern not found')
    idx = content.find('seed-demo')
    if idx >= 0:
        print(repr(content[idx-10:idx+60]))