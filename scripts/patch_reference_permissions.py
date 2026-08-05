from pathlib import Path

path = Path("deploy/server-deploy.sh")
text = path.read_text(encoding="utf-8")

before_import_old = '''rm -rf /opt/kayi-reference-data/normalized
mkdir -p /opt/kayi-reference-data/normalized
install -m 600 "$PRICE_FIXTURE" /opt/kayi-reference-data/kayi-prices.compact.xz
install -m 600 reference_data/encrypted/manifest.json /opt/kayi-reference-data/secure-manifest.json
'''

before_import_new = '''rm -rf /opt/kayi-reference-data/normalized
# The application container runs as UID/GID 10001. Give only that identity
# temporary access to the decrypted fixture and its writable output directory.
chmod 0711 /opt/kayi-reference-data
install -d -m 0700 -o 10001 -g 10001 /opt/kayi-reference-data/normalized
install -m 0400 -o 10001 -g 10001 "$PRICE_FIXTURE" /opt/kayi-reference-data/kayi-prices.compact.xz
install -m 0600 reference_data/encrypted/manifest.json /opt/kayi-reference-data/secure-manifest.json
'''

after_import_old = '''test "$(find /opt/kayi-reference-data/normalized -type f | wc -l)" -eq 25

dc up -d --remove-orphans
'''

after_import_new = '''test "$(find /opt/kayi-reference-data/normalized -type f | wc -l)" -eq 25
# The importer no longer needs host-side write access. Return all decrypted
# and normalized host files to root-only ownership after a verified import.
chown -R root:root /opt/kayi-reference-data/normalized
find /opt/kayi-reference-data/normalized -type d -exec chmod 0700 {} \\;
find /opt/kayi-reference-data/normalized -type f -exec chmod 0600 {} \\;
chown root:root /opt/kayi-reference-data/kayi-prices.compact.xz
chmod 0600 /opt/kayi-reference-data/kayi-prices.compact.xz

dc up -d --remove-orphans
'''

for old, new, label in (
    (before_import_old, before_import_new, "pre-import permissions"),
    (after_import_old, after_import_new, "post-import lockdown"),
):
    if new in text:
        continue
    if old not in text:
        raise RuntimeError(f"Expected deployment block not found: {label}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("Reference-data container permissions patched and verified.")
