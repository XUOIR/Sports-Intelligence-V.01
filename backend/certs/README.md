# Supabase database root CA

`supabase-ca.crt` is Supabase's public **Supabase Root 2021 CA** certificate, downloaded from the active project's **Database Settings → SSL configuration → Download certificate** on October 13, 2026. It contains no private key or environment secret.

- Official download: https://supabase-downloads.s3-ap-southeast-1.amazonaws.com/prod/ssl/prod-ca-2021.crt
- File SHA-256: `700723581420dd1ac98fd7e9ac529f0ef210eadcaf87fc868a3ad7d114c2f3b7`
- Valid until April 26, 2031 (UTC).
- Documentation: https://supabase.com/docs/guides/platform/ssl-enforcement

The backend loads this CA in addition to Python's default trust store. Certificate-chain and hostname verification remain enabled for both Alembic migrations and runtime connections. If Supabase rotates its root CA, replace this public certificate using the official Dashboard download, verify its source and validity, and redeploy the backend.
