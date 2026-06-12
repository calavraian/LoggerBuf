with open("/Users/calavraian/.gemini/antigravity/brain/7407098f-1d3f-45d5-8207-7114d62c8cc4/task.md", "r") as f:
    content = f.read()

content = content.replace("- [ ] 5", "- [x] 5")

with open("/Users/calavraian/.gemini/antigravity/brain/7407098f-1d3f-45d5-8207-7114d62c8cc4/task.md", "w") as f:
    f.write(content)
