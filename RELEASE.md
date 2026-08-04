# Release candidate

This branch is the first production release candidate for the KAYI Haustechnik operations platform. Merge is permitted only after the source-integrity check, migrations, Django checks, test suite, Python compilation and Docker Compose validation pass.

The release workflow validates its Compose configuration with the committed example environment before production secrets are injected on the server.
