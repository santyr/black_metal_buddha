# Private staging

The staging environment provides a separate application checkout, Unix service
account, and PostgreSQL database for provider preparation and release checks.
It binds to `127.0.0.1:8091`, with no public Nginx route or DNS change.

## Deployment plan

1. Copy the reviewed application source to `/opt/blackmetalbuddha/staging`,
   excluding Git metadata, credentials, databases, caches, and backups. Keep
   the existing installed dependencies at `/opt/blackmetalbuddha/venv` read-only.
2. Create Unix account and PostgreSQL login role `bmbstaging`, without superuser,
   database creation, or role creation privileges. Create database
   `blackmetalbuddha_staging` owned by that role; authenticate through the local
   PostgreSQL socket with peer authentication.
3. Install `deploy/staging.env.example` as
   `/etc/blackmetalbuddha-staging/staging.env`, mode `0640`, owned by
   `root:bmbstaging`, inside a `0750` directory with the same ownership.
4. Install and enable `blackmetalbuddha-staging.service`. Its startup applies
   Alembic migrations to the staging database before starting the web service.
   On SELinux hosts, restore default labels after copying files, before
   reloading systemd:

   ```bash
   sudo restorecon -RF /etc/systemd/system/blackmetalbuddha-staging.service \
     /etc/blackmetalbuddha-staging /opt/blackmetalbuddha/staging
   sudo systemctl daemon-reload
   sudo systemctl enable --now blackmetalbuddha-staging.service
   ```

5. Check health, storefront smoke checks, disabled checkout/admin/provider gates,
   migration head, database ownership, and denied access to production tables.

Production environment settings and services are not changed by this procedure.
No production credentials or customer data are copied. The staging catalog
starts empty; launch SKU reservations remain in the CSV for later setup.

## Access

From the server:

```bash
curl -fsS http://127.0.0.1:8091/healthz
bash deploy/smoke-test.sh http://127.0.0.1:8091
sudo systemctl status blackmetalbuddha-staging.service
sudo journalctl -u blackmetalbuddha-staging.service -n 50
```

From another computer, forward the loopback port using the owner's existing
SSH connection:

```bash
ssh -L 8091:127.0.0.1:8091 OWNER@SERVER
```

Then open `http://127.0.0.1:8091`. Use the actual SSH user and server address.

## Provider setup still required

Square remains in sandbox mode without credentials. Printful, email, checkout,
and admin remain disabled. Do not use production customer data or copy the
production environment file. Use separate sandbox Square credentials and a
designated Printful test store; Printful draft mode does not confirm production.

A public staging hostname, HTTPS endpoint, and signed webhook configuration
are needed for provider callbacks. The localhost instance does not prove those
callbacks or a real payment/fulfillment canary. It is the private staging
environment required before that provider work can proceed.

The staging instance has its own source snapshot. Refresh it from a reviewed
commit and restart the staging service before using it to validate a release.

## Installed evidence — 2026-10-02

- Staging service is enabled and active; `ExecStartPre` migrations succeeded.
- `ss` shows a listener only on `127.0.0.1:8091`.
- `/healthz` returns `200 ok`; the existing storefront smoke script passes.
- `/checkout` and `/admin` return 404; `/api/v1/catalog` returns 503.
- Database identity is `bmbstaging|blackmetalbuddha_staging`, migration head
  is `0007_refund_requests`, and the database contains zero orders.
- The staging role is denied access to production `product_variants`.
- The staging Unix account cannot read the production environment file.
- Production web, worker, PostgreSQL, and backup timer remain active.

The first systemd load failed because copying retained a `user_home_t` label
on the unit. `restorecon` applied the host's standard labels, after which the
service started successfully. SELinux remains enforcing.
