#!/bin/sh
set -eu

export DEBIAN_FRONTEND=noninteractive

if ! command -v git >/dev/null 2>&1 || ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y git docker.io curl openssl python3 coreutils
fi

systemctl enable --now docker

if ! docker compose version >/dev/null 2>&1; then
  apt-get update
  apt-get install -y docker-compose-v2 || apt-get install -y docker-compose-plugin || apt-get install -y docker-compose
fi

# Keep SSH untouched; only add explicit web ingress rules when a host firewall exists.
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
# The assembled application creates untracked source files. Remove them before
# reconstructing the next release so deployment remains idempotent.
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

dc build --pull
dc up -d db redis
dc run --rm web python manage.py migrate --noinput
dc run --rm web python manage.py bootstrap_admin --credentials-file /runtime/admin_credentials.txt
dc run --rm web python manage.py seed_demo_data --credentials-file /runtime/demo_credentials.txt

# Commercial pricing data is committed only as ciphertext. The RSA private key
# is generated once on the production host and never leaves /opt/kayi-secrets.
PRIVATE_KEY=/opt/kayi-secrets/reference-private.pem
if [ ! -s "$PRIVATE_KEY" ]; then
  echo "Missing production reference-data private key: $PRIVATE_KEY" >&2
  exit 1
fi

TMP_PRICE_B64=/tmp/kayi-prices.enc.b64
TMP_PRICE_ENC=/tmp/kayi-prices.enc
TMP_KEY_ENC=/tmp/kayi-reference-key.enc
TMP_PASSPHRASE=/tmp/kayi-reference-passphrase
PRICE_FIXTURE=/opt/kayi-reference-data/kayi-prices.compact.xz

{
  head -c 8000 reference_data/encrypted/prices.part-00
  cat reference_data/encrypted/prices.part-01 \
      reference_data/encrypted/prices.part-02 \
      reference_data/encrypted/prices.part-03 \
      reference_data/encrypted/prices.part-04 \
      reference_data/encrypted/prices.part-05
} > "$TMP_PRICE_B64"
printf '%s  %s\n' \
  'fba909127ab186258355cb76de5a73ddfdf5e78a5aa92a5e182f7a6f5b3525d0' \
  "$TMP_PRICE_B64" | sha256sum --check
base64 --decode "$TMP_PRICE_B64" > "$TMP_PRICE_ENC"
printf '%s  %s\n' \
  'e1906a43c44023045e772e8921c51fb1acd9f26e3d9c91838b842fc9c3ef3651' \
  "$TMP_PRICE_ENC" | sha256sum --check

base64 --decode reference_data/encrypted/key.enc.b64 > "$TMP_KEY_ENC"
printf '%s  %s\n' \
  '7f411bb00e4e2a7f478c5987529761e3eda2233a94e70d5f74fef55b96607e1a' \
  "$TMP_KEY_ENC" | sha256sum --check

openssl pkeyutl -decrypt \
  -inkey "$PRIVATE_KEY" \
  -in "$TMP_KEY_ENC" \
  -out "$TMP_PASSPHRASE" \
  -pkeyopt rsa_padding_mode:oaep \
  -pkeyopt rsa_oaep_md:sha256
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -in "$TMP_PRICE_ENC" \
  -out "$PRICE_FIXTURE" \
  -pass file:"$TMP_PASSPHRASE"
chmod 600 "$PRICE_FIXTURE"
printf '%s  %s\n' \
  'dccc8196e83fbd1f4d5471c4c885b35adf3ba627d819068ab154c3e1b2361aac' \
  "$PRICE_FIXTURE" | sha256sum --check

if command -v shred >/dev/null 2>&1; then
  shred -u "$TMP_PASSPHRASE" "$TMP_KEY_ENC" "$TMP_PRICE_ENC" "$TMP_PRICE_B64"
else
  rm -f "$TMP_PASSPHRASE" "$TMP_KEY_ENC" "$TMP_PRICE_ENC" "$TMP_PRICE_B64"
fi

dc run --rm \
  -v /opt/kayi-reference-data:/reference-data \
  web python manage.py import_normalized_prices \
  /reference-data/kayi-prices.compact.xz \
  --output-dir /reference-data/normalized

# Exact future vendor files can be dropped into this private host directory and
# will be ingested without ever entering the public repository.
if find /opt/kayi-reference-data/raw -type f \( \
  -iname '*.xlsx' -o -iname '*.xlsm' -o -iname '*.csv' -o \
  -iname '*.pdf' -o -iname '*.003' -o -iname '*.p86' \
\) -print -quit | grep -q .; then
  dc run --rm \
    -v /opt/kayi-reference-data/raw:/reference-data/raw:ro \
    web python manage.py import_reference_data /reference-data/raw
fi

# Fail the release if the real and demo datasets are not both present.
dc run --rm web python manage.py shell -c "
from django.contrib.auth import get_user_model
from erp.models import CalendarEvent, Organization, PriceItem, PriceSource
real = Organization.objects.exclude(settings__is_demo=True).first()
demo = Organization.objects.filter(settings__is_demo=True).first()
assert real is not None, 'real organization missing'
assert demo is not None, 'demo organization missing'
assert PriceSource.objects.filter(organization=real).count() >= 25, 'price sources incomplete'
assert PriceItem.objects.filter(organization=real).count() >= 3614, 'price rows incomplete'
assert CalendarEvent.objects.filter(organization=demo).count() >= 5, 'demo calendar incomplete'
assert get_user_model().objects.filter(username='demo').exists(), 'demo user missing'
print('KAYI data verification:', PriceSource.objects.filter(organization=real).count(), 'sources,', PriceItem.objects.filter(organization=real).count(), 'price rows,', CalendarEvent.objects.filter(organization=demo).count(), 'demo appointments')
"

dc up -d --remove-orphans

for attempt in $(seq 1 36); do
  if curl -fsS http://127.0.0.1/api/health/ >/dev/null; then
    echo "KAYI deployment healthy"
    echo "Normalized reference files on host: $(find /opt/kayi-reference-data/normalized -type f | wc -l)"
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
