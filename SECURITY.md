# Security policy

Do not open public issues containing customer information, credentials, invoice data, portal screenshots or access tokens.

## Secrets

Secrets belong in GitHub Actions secrets or the production `.env` file. Never commit `.env`, browser session state, GMX passwords, B&O credentials or OpenAI keys.

## Reporting

Report a vulnerability privately to the repository owner. Include the affected route, required role, reproduction steps and impact. Avoid accessing or modifying real customer data while testing.

## Operational controls

- rotate the current root password after SSH-key deployment is configured
- prefer a dedicated non-root deployment account and SSH key over password authentication
- make the repository private before adding proprietary catalogs or business documents
- change the bootstrap administrator password immediately
- review audit logs and failed automation jobs regularly
