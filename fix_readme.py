content = "---\ntitle: LMTrade Bot\nemoji: 📈\ncolorFrom: blue\ncolorTo: green\nsdk: docker\npinned: false\n---\n"
with open("README.md", "w", encoding="utf-8") as f:
    f.write(content)
print("OK")