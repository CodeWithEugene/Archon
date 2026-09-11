# Contributing Guidelines

Thank you for contributing to our submission for the **Nebius x NVIDIA Global AI Hackathon**! 

We welcome contributions from developers, researchers, designers, and testers. To ensure rapid progress, clean collaboration, and full compliance with the hackathon rules, please follow the guidelines below.

---

## Code of Conduct

We are committed to maintaining a welcoming, inclusive, and collaborative environment. All contributors are expected to:
- Be respectful, constructive, and open to diverse technical viewpoints.
- Focus on practical, high-impact problem solving.
- Uphold academic and professional integrity—no plagiarism or unlicensed third-party code.

---

## Hackathon Architecture & Project Layout

The repository is structured into two main operational pillars:
```
.
├── 0.docs/                # Project documentation, research, and hackathon dossier
│   ├── info.md            # Comprehensive hackathon reference dossier
│   └── problem+solution.md # Target problem definition, architecture, and value proposition
├── 1.platform/            # Working software implementation
│   ├── client/            # User-facing frontend application (UI/UX)
│   └── server/            # Backend agent core, model orchestration, and API endpoints
├── CONTRIBUTING.md        # Contribution rules and workflow (this file)
├── LICENSE.md             # Apache 2.0 open-source license
├── README.md              # Project overview, quickstart, and hackathon submission details
└── SECURITY.md            # AI security, secret protection, and sandbox policies
```

---

## Development Workflow

### 1. Branching Strategy
We adhere to a lightweight git workflow:
- `main`: The stable, production-ready release branch submitted to Devpost.
- `develop` (optional): Staging branch for active feature consolidation.
- Feature branches should follow semantic naming:
  - `feat/<short-feature-name>`: New feature or agent capability
  - `fix/<short-bug-name>`: Bug fix or stability improvement
  - `docs/<short-description>`: Documentation and cookbook updates
  - `perf/<short-description>`: Latency, token optimization, or compute speedup

### 2. Commit Message Conventions
We follow the **Conventional Commits** specification:
```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```
Common types:
- `feat`: A new feature (e.g. `feat(agent): add dynamic hybrid router for Nemotron 3 Ultra`)
- `fix`: A bug fix (e.g. `fix(client): handle SSE disconnect gracefully in chat window`)
- `docs`: Documentation changes (e.g. `docs(readme): add setup guide for Tavily API key`)
- `refactor`: Code refactoring without behavioral alterations
- `test`: Adding or refactoring unit/integration tests
- `chore`: Dependency upgrades, tool configs, or repo maintenance

### 3. Environment & Secrets Management
- **Never commit `.env` or credentials.**
- Always copy `.env.example` to `.env.local` or `.env` and fill in local keys:
  ```bash
  NEBIUS_API_KEY=your_token_factory_key
  TAVILY_API_KEY=your_tavily_key
  ```

---

## Code Quality & Judging Alignment

Every pull request should directly advance our score across the four Hackathon Judging Criteria:

1. **Technological Implementation (25%):**
   - Is the code robust, modular, and error-handled?
   - Does it cleanly leverage **Nebius Token Factory** endpoints or **Nebius AI Cloud** compute?
   - Does it effectively incorporate **NVIDIA Nemotron** or other NVIDIA open models?
2. **Design & UX (25%):**
   - Is the user interface polished, reactive, and intuitive?
   - Are streaming responses and agent thoughts transparently visualized?
3. **Potential Impact (25%):**
   - Does the contribution tangibly solve the core user pain point?
4. **Quality of the Idea (25%):**
   - Does the implementation push the boundaries of open AI infrastructure?

---

## Submitting a Pull Request (PR)

1. Ensure your code passes all lint checks, type checks, and tests:
   ```bash
   npm run lint # or pytest / ruff for Python services
   ```
2. Rebase or merge the latest changes from `main`.
3. Open a PR with a clear, descriptive title and bullet points covering:
   - What changed and why.
   - Any new environment variables introduced.
   - Verification steps and screenshots/recordings if UI changes were made.
4. Request review from at least one teammate before merging.
