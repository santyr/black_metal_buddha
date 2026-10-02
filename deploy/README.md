# Phase 0 Production Deployment

This runbook deploys the pre-launch Black Metal Buddha catalog. Checkout remains disabled.

The Phase 0 application is stateless and does **not** require PostgreSQL yet. A database is introduced with the transactional order system in Phase 1.

## 1. DNS

Point the apex domain and, if used, `www` at the VPS.

Do not publish an AAAA record unless IPv6 is actually reachable on the VPS.

Canonical public URL:

```
https://blackmetalbuddha.com
```

## 2. Service account and checkout

Example layout expected by the supplied systemd unit:

```
/opt/blackmetalbuddha/current
/opt/blackmetalbuddha/venv
/etc/blackmetalbuddha/blackmetalbuddha.env
```

Example setup:

```bash
sudo useradd --system --home-dir /opt/blackmetalbuddha --shell /usr/sbin/nologin blackmetalbuddha || true
sudo install -d -o blackmetalbuddha -g blackmetalbuddha /opt/blackmetalbuddha

sudo -u blackmetalbuddha git clone \
  https://github.com/santyr/black_metal_buddha.git \
  /opt/blackmetalbuddha/current

sudo -u blackmetalbuddha python3 -m venv /opt/blackmetalbuddha/venv
sudo -u blackmetalbuddha /opt/blackmetalbuddha/venv/bin/pip install \
  -r /opt/blackmetalbuddha/current/requirements.txt
```

## 3. Production environment

```bash
sudo install -d -m 0750 -o root -g blackmetalbuddha /etc/blackmetalbuddha
sudo cp /opt/blackmetalbuddha/current/.env.example \
  /etc/blackmetalbuddha/blackmetalbuddha.env
sudo chown root:blackmetalbuddha /etc/blackmetalbuddha/blackmetalbuddha.env
sudo chmod 0640 /etc/blackmetalbuddha/blackmetalbuddha.env
```

Confirm:

```
APP_ENV=production
PUBLIC_BASE_URL=https://blackmetalbuddha.com
```

## 4. systemd

```bash
sudo cp /opt/blackmetalbuddha/current/deploy/systemd/blackmetalbuddha.service \
  /etc/systemd/system/blackmetalbuddha.service
sudo systemctl daemon-reload
sudo systemctl enable --now blackmetalbuddha.service
sudo systemctl status blackmetalbuddha.service
curl -fsS http://127.0.0.1:8088/healthz
```

Expected health response:

```
ok
```

## 5. Nginx and TLS

The supplied vhost lives at:

```
deploy/nginx/blackmetalbuddha.conf
```

Install it using the VPS's existing Nginx layout. Add the certificate directives used by the existing certificate workflow before enabling the HTTPS servers.

Then validate and reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

The configuration redirects HTTP and `www` to the canonical HTTPS apex domain.

HSTS is intentionally commented out. Enable it only after the certificate and HTTPS redirects are verified.

## 6. Public smoke test

From any machine with public network access:

```bash
./deploy/smoke-test.sh https://blackmetalbuddha.com
```

The script checks health, homepage branding, the approved logo, security headers, robots.txt, sitemap.xml, and one product page.

## 7. Updating Phase 0

```bash
sudo -u blackmetalbuddha git -C /opt/blackmetalbuddha/current pull --ff-only
sudo -u blackmetalbuddha /opt/blackmetalbuddha/venv/bin/pip install \
  -r /opt/blackmetalbuddha/current/requirements.txt
sudo systemctl restart blackmetalbuddha.service
curl -fsS http://127.0.0.1:8088/healthz
```

Run the public smoke test after every deployment.

## 8. Rollback

Record the previously deployed commit before updating.

If a deployment fails, check out that known-good commit, reinstall requirements if necessary, restart the service, and run both local and public health checks.

## Phase 0 boundary

Do not add Square or Printful secrets to this environment yet. No checkout, customer order, or payment flow should be enabled until Phase 1.


---

# Phase 1 additions

For transactional deployment, also install:

```
deploy/systemd/blackmetalbuddha-worker.service
deploy/systemd/blackmetalbuddha-reconcile.service
deploy/systemd/blackmetalbuddha-reconcile.timer
deploy/systemd/blackmetalbuddha-backup.service
deploy/systemd/blackmetalbuddha-backup.timer
```

Apply database migrations before restarting Phase 1 code:

```bash
sudo -u blackmetalbuddha /opt/blackmetalbuddha/venv/bin/alembic \
  -c /opt/blackmetalbuddha/current/alembic.ini upgrade head
```

After public transactional launch:

```bash
bash /opt/blackmetalbuddha/current/deploy/phase1-smoke-test.sh \
  https://blackmetalbuddha.com
```

See `docs/24_PHASE1_LAUNCH_RUNBOOK.md` for catalog fingerprinting, production canary, backup/restore verification, final activation, and emergency shutdown.

## Private staging

The deployed private staging instance uses a separate source checkout, Unix
account, and PostgreSQL database and listens only on `127.0.0.1:8091`.
Its service definition is `deploy/systemd/blackmetalbuddha-staging.service`;
safe initial settings are in `deploy/staging.env.example`.

See `docs/27_PRIVATE_STAGING.md` for the deployment procedure, SSH forwarding,
verified isolation, and remaining provider callback setup.
