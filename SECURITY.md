# Security Policy

## Product Context & Scope
Permit Delta is a local decision-support visual workspace for production location review. This tool is **not** legal advice, nor does it provide autonomous compliance or legal approval. Always consult official park authorities, county permitting offices, or the California Film Commission (CFC) for final binding determinations.

## Safe Handling of Secrets and Credentials
To maintain rigorous security and avoid accidental exposure of sensitive API keys or credentials, follow these guidelines:

1. **No Embedded Keys**: Never hardcode API keys, service account credentials, or bearer tokens in any application source, configuration files, frontend bundles, logs, or screenshots.
2. **Environment Variables & ADC**: Use Google Cloud Application Default Credentials (ADC) for Gemini Vertex AI along with the necessary project identifier environment variables (`GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION`). Use `PARALLEL_API_KEY` for Parallel Search.
3. **Vertex AI Deployment**: In production (Vertex AI/Cloud Run), rely strictly on **Application Default Credentials (ADC)** and Cloud Run Service Accounts to obtain temporary, secure tokens.
4. **Local Verification**: Use `.env` files for local development. Never commit `.env` files to git. A template with empty variable names is provided as `.env.template`.

## Reporting a Vulnerability
If you discover a security vulnerability, please submit a report to the workspace administrator. Do not open public issues or public PRs containing vulnerability details.
