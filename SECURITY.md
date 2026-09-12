# Security Policy

## Reporting a vulnerability

If you find a security problem in this repository, including an exposed credential, please do not open a public issue. Email the maintainer listed in the GitHub repository profile with a description, reproduction steps, and impact. You will get an acknowledgement within 48 hours.

---

## Threat model

ARCHON runs model-generated code against untrusted repositories, calls third-party APIs with paid credentials, and exposes a public demo. The controls below follow from that.

### 1. Credentials

- `NEBIUS_API_KEY`, `NEBIUS_PROJECT_ID`, `TAVILY_API_KEY`, `LANGSMITH_API_KEY`, and `ARCHON_DEMO_TOKEN` live only in server-side environment variables. They are never sent to the browser, logged, or committed.
- `.env*` files are ignored by `.gitignore`. Only `.env.example`, with empty values, is tracked.
- ARCHON does not accept or store GitHub personal access tokens. Verified patches are delivered as downloadable `.patch` files with `git apply` instructions rather than pushed on the user's behalf.

### 2. Code execution

- All repository code, dependency installs, and test runs execute inside **Nebius Token Factory Sandboxes**, which are VM-isolated and hosted by Nebius. Nothing from a target repository runs on the ARCHON server.
- Each candidate patch runs on its own sandbox fork. Failed forks are discarded; the baseline checkpoint is never mutated.
- Every mission has a hard iteration limit and a hard spend cap. Both are enforced server-side.
- Sandboxes are in beta. Per Nebius guidance, do not upload personal or sensitive data into them.

### 3. Prompt injection and model output

- Content fetched from the web through Tavily and content read from target repositories are treated as untrusted data. They are placed in clearly delimited context blocks and never as system instructions.
- Model outputs that request tool calls are validated against strict Pydantic schemas before execution. Unknown tools or malformed arguments are rejected.
- Patches are applied only inside a sandbox, only after syntax validation, and only surfaced to the user after the reviewer step and a passing test run.

### 4. Tracing

- LangSmith tracing is off unless `LANGSMITH_API_KEY` is set. When on, prompts, model outputs, and scrubbed sandbox results are sent to LangSmith. Do not enable it for missions on repositories whose contents must not leave the deployment.

### 5. Public demo

- The public demo defaults to **replay mode**, which streams recorded mission traces and makes no paid API calls.
- **Live mode** requires `ARCHON_DEMO_TOKEN`, is rate-limited per IP, and is bounded by `ARCHON_MAX_MISSION_USD`.
- Repository input is limited to public `https://github.com/...` URLs and SWE-bench Verified instance IDs. Local paths and arbitrary URLs are rejected.

---

## Compliance

This project follows the Nebius x NVIDIA Global AI Hackathon rules. Any security testing must target locally hosted instances and must not disrupt shared Nebius, Tavily, or Devpost services.
