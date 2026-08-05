#!/bin/sh
set -eu

export DEBIAN_FRONTEND=noninteractive

if ! command -v git >/dev/null 2>&1 || ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y git docker.io curl openssl python3 coreutils xz-utils
fi

systemctl enable --now docker

if ! docker compose version >/dev/null 2>&1; then
  apt-get update
  apt-get install -y docker-compose-v2 || apt-get install -y docker-compose-plugin || apt-get install -y docker-compose
fi

if command -v ufw >/dev/null 2>&1; then
  ufw allow 80/tcp >/dev/null 2>&1 || true
  ufw allow 443/tcp >/dev/null 2>&1 || true
  ufw allow 443/udp >/dev/null 2>&1 || true
fi
if command -v iptables >/dev/null 2>&1; then
  iptables -C INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -p tcp --dport 80 -j ACCEPT
  iptables -C INPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -p tcp --dport 443 -j ACCEPT
  iptables -C INPUT -p udp --dport 443 -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -p udp --dport 443 -j ACCEPT
fi

dc() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  else
    docker-compose "$@"
  fi
}

mkdir -p \
  /opt/kayi \
  /opt/kayi-backups \
  /opt/kayi-reference-data/raw \
  /opt/kayi-reference-data/normalized \
  /opt/kayi-secrets
chmod 700 /opt/kayi-secrets

if [ ! -d /opt/kayi/.git ]; then
  rm -rf /opt/kayi/*
  git clone https://github.com/hsdarestani/KAYIHAUSTECHNIK.git /opt/kayi
fi

cd /opt/kayi
git fetch origin main
git reset --hard origin/main
# Source assembly creates untracked application files. Remove only generated
# files while preserving the host-only production environment.
git clean -fdx -e .env
bash scripts/unpack-source.sh

umask 077
if [ ! -f .env ]; then
  DJANGO_SECRET_KEY="$(openssl rand -hex 48)"
  POSTGRES_PASSWORD="$(openssl rand -hex 32)"
  printf '%s\n' \
    "DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}" \
    "DEBUG=0" \
    "ALLOWED_HOSTS=kayi.smarbiz.sbs,91.107.144.64,localhost,127.0.0.1" \
    "CSRF_TRUSTED_ORIGINS=https://kayi.smarbiz.sbs,http://91.107.144.64" \
    "SECURE_SSL_REDIRECT=0" \
    "COOKIE_SECURE=0" \
    "TIME_ZONE=Europe/Berlin" \
    "POSTGRES_DB=kayi" \
    "POSTGRES_USER=kayi" \
    "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}" \
    "POSTGRES_HOST=db" \
    "POSTGRES_PORT=5432" \
    "CELERY_BROKER_URL=redis://redis:6379/0" \
    "CELERY_RESULT_BACKEND=redis://redis:6379/1" \
    "OPENAI_API_KEY=" \
    "OPENAI_MODEL=gpt-5" \
    "ORGANIZATION_NAME=KAYI Haustechnik" \
    "INITIAL_ADMIN_USERNAME=admin" \
    "INITIAL_ADMIN_EMAIL=admin@kayi.local" > .env
fi

python3 - <<'PY'
import os
from pathlib import Path

path = Path('.env')
lines = path.read_text().splitlines()
values = {}
order = []
for line in lines:
    if '=' in line and not line.lstrip().startswith('#'):
        key, value = line.split('=', 1)
        values[key] = value
        order.append(key)
values['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY', '')
if 'OPENAI_API_KEY' not in order:
    order.append('OPENAI_API_KEY')
path.write_text('\n'.join(f'{key}={values[key]}' for key in order) + '\n')
path.chmod(0o600)
PY

if dc ps --status running --services 2>/dev/null | grep -q '^db$'; then
  dc exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "/opt/kayi-backups/predeploy-$(date +%Y%m%d-%H%M%S).sql.gz" || true
  find /opt/kayi-backups -type f -mtime +14 -delete || true
fi

# Build from the exact tested source. Avoid an unnecessary base-image pull on
# every release so a temporary registry interruption cannot break production.
dc build
dc up -d db redis
dc run --rm web python manage.py migrate --noinput
dc run --rm web python manage.py bootstrap_admin --credentials-file /runtime/admin_credentials.txt
dc run --rm web python manage.py seed_demo_data --credentials-file /runtime/demo_credentials.txt
dc run --rm web python manage.py shell -c "from erp.models import Organization; Organization.objects.get_or_create(name='KAYI Haustechnik', defaults={'settings': {}})"

PRIVATE_KEY=/opt/kayi-secrets/reference-private.pem
if [ ! -s "$PRIVATE_KEY" ]; then
  echo "Missing production reference-data private key: $PRIVATE_KEY" >&2
  exit 1
fi
PUBLIC_KEY_HASH="$(openssl pkey -in "$PRIVATE_KEY" -pubout -outform DER 2>/dev/null | sha256sum | awk '{print $1}')"
if [ "$PUBLIC_KEY_HASH" != "cd1ce6b1ca51d079b417b42e96d582c70363bef0ba42cc1e408ffc64ba225b03" ]; then
  echo "Production reference-data key mismatch" >&2
  exit 1
fi

TMP_ROOT="$(mktemp -d /tmp/kayi-reference-release.XXXXXX)"
cleanup_sensitive() {
  if command -v shred >/dev/null 2>&1; then
    find "$TMP_ROOT" -type f -exec shred -u {} \; 2>/dev/null || true
  fi
  rm -rf "$TMP_ROOT"
}
trap cleanup_sensitive EXIT INT TERM

PAYLOAD_B64="$TMP_ROOT/payload.b64"
PAYLOAD_ENC="$TMP_ROOT/payload.enc"
WRAPPED_KEY="$TMP_ROOT/key.enc"
PASSPHRASE="$TMP_ROOT/passphrase"
ARCHIVE="$TMP_ROOT/kayi-reference-data.tar.xz"
EXTRACTED="$TMP_ROOT/extracted"
mkdir -p "$EXTRACTED"

cat reference_data/encrypted/payload.part-* > "$PAYLOAD_B64"
test "$(wc -c < "$PAYLOAD_B64")" -eq 814296
printf '%s  %s\n' \
  'ffd3e1333e003e0360b747d1d0b1d56272a4824b430b0dd3fa9a91033a911821' \
  "$PAYLOAD_B64" | sha256sum --check
base64 --decode "$PAYLOAD_B64" > "$PAYLOAD_ENC"
test "$(wc -c < "$PAYLOAD_ENC")" -eq 610720
printf '%s  %s\n' \
  'c1ab1aa6667f84700019b420b4d677726f674f63802e066c2ceb88bef84ace38' \
  "$PAYLOAD_ENC" | sha256sum --check

base64 --decode reference_data/encrypted/key.enc.b64 > "$WRAPPED_KEY"
printf '%s  %s\n' \
  '6a699ce73d98968a2333e9f773cdda3c9cd3e1c452bb19075dcaf6f77996710c' \
  "$WRAPPED_KEY" | sha256sum --check
openssl pkeyutl -decrypt \
  -inkey "$PRIVATE_KEY" \
  -in "$WRAPPED_KEY" \
  -out "$PASSPHRASE" \
  -pkeyopt rsa_padding_mode:oaep \
  -pkeyopt rsa_oaep_md:sha256
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -in "$PAYLOAD_ENC" \
  -out "$ARCHIVE" \
  -pass file:"$PASSPHRASE"
test "$(wc -c < "$ARCHIVE")" -eq 610700
printf '%s  %s\n' \
  '51c88dd4f5987e14c406e95545b3323214480506f0d08e64b91a4337550f0770' \
  "$ARCHIVE" | sha256sum --check

tar --no-same-owner -xJf "$ARCHIVE" -C "$EXTRACTED"
test -f "$EXTRACTED/kayi-prices.compact.xz"
test -f "$EXTRACTED/manifest.json"
RAW_COUNT="$(find "$EXTRACTED/stammdaten" -type f | wc -l)"
if [ "$RAW_COUNT" -ne 10 ]; then
  echo "Expected 10 exact XLSX/CSV source files, found $RAW_COUNT" >&2
  exit 1
fi

rm -rf /opt/kayi-reference-data/raw/stammdaten /opt/kayi-reference-data/normalized
mkdir -p /opt/kayi-reference-data/raw /opt/kayi-reference-data/normalized
cp -a "$EXTRACTED/stammdaten" /opt/kayi-reference-data/raw/
install -m 600 "$EXTRACTED/kayi-prices.compact.xz" /opt/kayi-reference-data/kayi-prices.compact.xz
install -m 600 "$EXTRACTED/manifest.json" /opt/kayi-reference-data/manifest.json
install -m 600 reference_data/encrypted/manifest.json /opt/kayi-reference-data/secure-manifest.json

dc run --rm \
  -v /opt/kayi-reference-data:/reference-data \
  web python manage.py import_normalized_prices \
  /reference-data/kayi-prices.compact.xz \
  --output-dir /reference-data/normalized

# Release gates: production and demo data must be present and separated. A
# failed assertion stops deployment before the new web containers replace the
# currently running version.
dc run --rm web python manage.py shell -c "
from django.contrib.auth import get_user_model
from erp.models import CalendarEvent, CatalogItem, Organization, PriceItem, PriceSource
real = Organization.objects.filter(name='KAYI Haustechnik').first()
demo = Organization.objects.filter(settings__is_demo=True).first()
assert real is not None, 'real organization missing'
assert demo is not None, 'demo organization missing'
assert PriceSource.objects.filter(organization=real).count() == 25, 'price sources incomplete'
assert PriceItem.objects.filter(organization=real).count() == 13020, 'price rows incomplete'
assert CatalogItem.objects.filter(organization=real).count() >= 219, 'catalog incomplete'
assert CalendarEvent.objects.filter(organization=demo).count() >= 5, 'demo calendar incomplete'
assert get_user_model().objects.filter(username='demo').exists(), 'demo user missing'
print('KAYI release data verified:', 25, 'sources,', 13020, 'price rows')
"

test "$(find /opt/kayi-reference-data/raw/stammdaten -type f | wc -l)" -eq 10
test "$(find /opt/kayi-reference-data/normalized -type f | wc -l)" -eq 25

dc up -d --remove-orphans

for attempt in $(seq 1 36); do
  if curl -fsS http://127.0.0.1/api/health/ >/dev/null; then
    echo "KAYI deployment healthy"
    echo "Exact XLSX/CSV files on host: $(find /opt/kayi-reference-data/raw/stammdaten -type f | wc -l)"
    echo "Normalized searchable source files: $(find /opt/kayi-reference-data/normalized -type f | wc -l)"
    dc ps
    ss -lntup 2>/dev/null | grep -E '(:80|:443)' || true
    docker image prune -f
    exit 0
  fi
  if [ "$attempt" -eq 36 ]; then
    dc logs --tail=250 web caddy worker beat
    exit 1
  fi
  sleep 5
done
