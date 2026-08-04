# KAYI Production Release v2.1

Released: 2026-08-05

## GitHub Actions

- Production workflow run: `30974736583`
- Successful retry job: `92205826690`
- Validation completed before SSH deployment: source integrity, committed migrations, Django checks, full tests, Python compile and Docker Compose validation.

## Production verification

The deployment command completed with these verified production values:

- 25 versioned commercial price sources
- 3,614 searchable normalized price rows
- 25 normalized server-side reference files
- isolated `KAYI Demo` organization and `demo` user
- 5 demo calendar appointments
- internal application health check successful
- public IP health check successful
- domain DNS and HTTPS check successful

## Delivered product changes

- dedicated protected calendar with week, day, month and employee views
- suppliers, payments and versioned price-library interfaces
- encrypted transfer and server-side import of the ZIP price/reference data
- operational catalog population from the KAYI service catalog
- isolated sample customers, projects, tasks, appointments, invoice and payment
- mobile token API, privacy policy, terms, account deletion and Capacitor mobile scaffold

No plaintext commercial pricing data or credentials are stored in the public repository. The RSA private key remains only on the production server.
