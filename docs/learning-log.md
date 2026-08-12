# Learning Log

This document records what I learn while building the Research Intelligence Workspace.

The learning process is:

> Concept → Tiny Experiment → Understand → Implement → Document → Commit

---

## Phase 0 — Foundation

### Git & GitHub

**Learned:**

- A Git repository tracks changes to a project.
- The local repository is the copy on my computer.
- The remote repository is the GitHub copy.
- `git clone` creates a local copy connected to the remote.
- `git add` stages changes.
- `git commit` creates a local checkpoint.
- `git push` sends commits to GitHub.
- Git tracks files rather than empty directories.

**Understanding:**

Git is not simply a tool for uploading files. It is a version-control system that allows a project's changes to be tracked through checkpoints.

---

### Python Virtual Environment

**Learned:**

- A virtual environment isolates project dependencies.
- `venv` creates the environment.
- Activation makes the terminal use that environment.
- Packages installed with `pip` are installed into the active environment.
- `.venv` should not be committed to GitHub.

**Understanding:**

A virtual environment keeps the dependencies of this project separate from other Python projects on my computer.

---

### Frontend & Backend

**Learned:**

- The frontend is the user-facing part of the application.
- The backend handles server-side application logic.
- The frontend and backend communicate through APIs.

**Understanding:**

The frontend does not need to know how the backend performs its internal work. It communicates with the backend through defined API endpoints.

---

### HTTP

**Learned:**

- HTTP is a protocol used for client-server communication.
- A client sends a request.
- A server processes the request and returns a response.
- Requests can contain methods, URLs, headers and bodies.
- Responses contain data and status codes.

Important methods:

- GET
- POST
- PUT
- PATCH
- DELETE

---

### REST & APIs

**Learned:**

- An API defines how software can communicate with another system.
- REST is a common architectural style for designing APIs around resources and HTTP methods.
- JSON is commonly used to exchange structured data.

Example:

```text
POST /research
```
