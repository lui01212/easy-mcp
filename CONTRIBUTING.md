# Contributing to easy-mcp

Thank you for your interest in **easy-mcp**! We welcome contributions to make building Model Context Protocol servers as easy and accessible as possible.

---

## 🌟 Great First Issues

- **Add an MCP server example in `examples/`:**
  Build a small tool server (e.g., SQLite query, currency converter, file search, RSS reader).
- **Add unit tests:**
  Add test cases in `tests/test_server.py`.
- **Improve schema parsing:**
  Support additional type annotations in `easy_mcp/schema.py`.

---

## 🛠️ Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/<your-username>/easy-mcp.git
   cd easy-mcp
   ```

2. **Zero external dependencies:**
   `easy-mcp` is 100% standard library Python. No heavy external frameworks required!

3. **Running tests:**
   ```bash
   python -m unittest discover tests
   ```

4. **Submitting changes:**
   - Create a branch: `git checkout -b feat/add-sqlite-example`
   - Test your changes: `python -m unittest`
   - Commit with Conventional Commits: `git commit -m "feat(examples): add sqlite query mcp server"`
   - Push and open a Pull Request!
