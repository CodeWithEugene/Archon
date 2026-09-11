# Security Policy

## Supported Versions

We actively monitor and provide security patches for the following versions:

| Version | Supported          | Status |
| ------- | ------------------ | ------ |
| 1.0.x   | :white_check_mark: | Active Hackathon Build |
| < 1.0   | :x:                | Deprecated / Development |

---

## Reporting a Vulnerability

The project team takes security, agentic isolation, and data privacy seriously. If you discover a security vulnerability or credential exposure in this repository, please report it responsibly:

1. **Do NOT file a public issue.**
2. Send an email to the repository maintainer or team lead with:
   - A description of the vulnerability.
   - Exact steps or code required to reproduce the behavior.
   - Any potential impact on agent isolation, data privacy, or infrastructure.
3. You will receive an initial response and acknowledgment within **48 hours**.
4. We will coordinate a patch and responsible public disclosure timeline once resolved.

---

## AI Agent & Infrastructure Security Guidelines

This repository interacts with high-performance AI inference backends (**Nebius Token Factory**), autonomous agent runtimes, and external search APIs (**Tavily**). All contributors and operators must strictly adhere to the following security principles:

### 1. Zero Credential Exposure
- **Never commit API keys or credentials** to git tracking. All keys must be passed through local `.env` files or secure runtime secrets.
- Required protected keys include:
  - `NEBIUS_API_KEY` (Nebius Token Factory & AI Cloud)
  - `TAVILY_API_KEY` (Tavily Search API)
  - `LANGSMITH_API_KEY` (LangChain Observability)
  - Any server authentication secrets or database connection strings.
- Always ensure `.env` and `*.key` files are explicitly listed in `.gitignore`.

### 2. Autonomous Agent Sandboxing
- Any dynamic code generation and execution triggered by coding agents **MUST execute in isolated sandboxes**:
  - In production / cloud: Use **Nebius Token Factory Sandboxes**.
  - In local / agentic deployments: Enforce **NVIDIA OpenShell** kernel-level sandboxing with strict declarative YAML access control policies.
- Restrict network egress from sandboxed environments to prevent arbitrary outbound data exfiltration.
- Mount file systems as read-only where possible, and strictly scope workspace write permissions.

### 3. Prompt Injection & Tool Guardrails
- Validate and sanitize all external web content retrieved via search or web scrapers before feeding it into model context windows.
- Restrict agent tool definitions with strict schema validation (e.g. Zod, Pydantic) to prevent unauthorized arbitrary parameter execution.
- Maintain human-in-the-loop validation for high-risk operations (e.g., file system deletions, financial actions, external communications).

---

## Responsible Disclosure & Compliance

This repository complies with the official rules and safety guidelines of the **Nebius x NVIDIA Global AI Hackathon**. Any security research or penetration testing must be conducted against locally hosted or controlled test instances, and must not disrupt shared Nebius Token Factory or Devpost services.
