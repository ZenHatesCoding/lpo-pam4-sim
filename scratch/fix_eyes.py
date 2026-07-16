with open('scratch/debug_eyes.py', 'r', encoding='utf-8') as f:
    text = f.read()
text = text.replace('\\"', '"')
with open('scratch/debug_eyes.py', 'w', encoding='utf-8') as f:
    f.write(text)
