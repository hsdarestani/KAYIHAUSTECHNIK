# Canonical source architecture

The assembled A+Bau application source is committed directly to Git and is the authoritative development, CI and deployment source.

## Normal development

Edit `erp/`, `config/`, `templates/`, `static/`, `mobile/`, `native/` and the other application files directly. Routine CI and production deployments use those tracked files as-is. They do **not** reconstruct the application from `.bootstrap/source.part-*` and the historical patch/install chain.

`scripts/verify-canonical-source.sh` is the fast checkout guard used by routine automation. It validates that the expected final source is present and tracked without mutating it.

## Legacy rebuild

`.bootstrap/`, `scripts/unpack-source.sh` and the historical installer scripts remain only as a compatibility/recovery path. To explicitly regenerate the old deterministic assembly, run:

```bash
bash scripts/rebuild-legacy-source.sh
```

A separate `Legacy source reproducibility` workflow checks the recovery path periodically and on demand. New product fixes must be made directly in canonical source rather than added as another historical patch layer.

## Why this changed

The old default path unpacked an archive and executed roughly fifty sequential mutation scripts, and some CI paths repeated that assembly in the same job. That made small fixes difficult to locate, allowed later layers to overwrite earlier changes, and added unnecessary work to every validation and deployment. The canonical model removes that hidden mutation chain from everyday work while preserving the old rebuild mechanism for recovery and reproducibility checks.
