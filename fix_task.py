with open("/Users/calavraian/.gemini/antigravity/brain/7407098f-1d3f-45d5-8207-7114d62c8cc4/task.md", "r") as f:
    content = f.read()

content = content.replace("- [ ] 1", "- [x] 1").replace("- [ ] 2", "- [x] 2").replace("- [ ] 3", "- [x] 3").replace("- [ ] 4", "- [x] 4").replace("- [ ] Add", "- [x] Add").replace("- [ ] Change", "- [x] Change").replace("- [ ] Implement", "- [x] Implement").replace("- [ ] Check", "- [x] Check")

with open("/Users/calavraian/.gemini/antigravity/brain/7407098f-1d3f-45d5-8207-7114d62c8cc4/task.md", "w") as f:
    f.write(content)
