# Copy this file to appconfig.py and fill in credentials.
# appconfig.py is gitignored (see .gitignore).
#
# On EC2, you can keep ICEBERG_USER / ICEBERG_PASSWORD empty here and set the same names in
# the systemd EnvironmentFile (e.g. from GitHub Actions secrets → deploy/runtime-secrets.env).
# Environment variables override these attributes.

ICEBERG_CATALOG_ENDPOINT = "https://ram-narayanan.com/iceberg-catalog"
# Basic auth (nginx). Whitespace is stripped. Use ICEBERG_USERNAME instead of ICEBERG_USER if you prefer.
ICEBERG_USER = "your-basic-auth-username"
ICEBERG_PASSWORD = "your-password"
# If the gateway expects a bearer token instead of Basic auth:
# ICEBERG_BEARER_TOKEN = "..."

# Warehouse name your REST catalog expects (common values: "warehouse", "main").
ICEBERG_WAREHOUSE = "warehouse"

# Alias used in SQL: iceberg_catalog.schema.table
CATALOG_ALIAS = "iceberg_catalog"

# Fully qualified cities table (default matches catalog: liewyousheng_geolocation).
# If your schema name differs, override — e.g. typo "i" vs "l" in the middle segment.
CITIES_TABLE_FQN = "iceberg_catalog.liewyousheng_geolocation.cities"

# Default CITY_COLUMNS match liewyousheng_geolocation.cities (id, name, state_name,
# country_name, latitude, longitude). Override only if your table differs.
# CITY_COLUMNS = { "state": "" }  # omit state column from search/labels if needed

# --- S3 access to Iceberg data files (avoid HTTP 403 on the warehouse bucket) ---
#
# On EC2, the app runs under systemd (often as root) with no ~/.aws profile. The Iceberg REST
# login (ICEBERG_USER/PASSWORD) does not grant S3 access — DuckDB must sign S3 requests using
# the instance IAM role or explicit keys. With no static keys below, the app now always uses
# DuckDB's credential_chain (instance metadata, env vars, etc.). Ensure the instance role can
# s3:GetObject (and ListBucket as needed) on the warehouse bucket/prefix, and set region:
#
# S3_REGION = "us-east-1"
# Optional: tune provider order (defaults work on many hosts; add `instance` if needed for IMDS):
# S3_CREDENTIAL_CHAIN = "env;instance;config;process"
#
# Option A — Use your normal AWS CLI session (`aws login`, `aws sso login`, profiles, env).
# 1) Set the flag below to True
# 2) In the same shell you use to start Python: run `aws login` / `aws sso login`, set
#    AWS_PROFILE if you use a named profile, then verify: aws sts get-caller-identity
# See: https://duckdb.org/docs/current/core_extensions/aws.html#credential_chain-provider
#
# S3_USE_AWS_CREDENTIAL_CHAIN = True
# When True, the app also runs `aws configure export-credentials --format env` by default
# (S3_SYNC_AWS_CLI_CREDENTIALS) so DuckDB gets the same keys + session token as the CLI.
# If `aws s3api head-object` works but DuckDB returned 403, that mismatch is why.
# Set S3_SYNC_AWS_CLI_CREDENTIALS = False to skip the subprocess, and instead run manually:
#   eval "$(aws configure export-credentials --format env)"
# Provider order (default below). Put env first if you export AWS_ACCESS_KEY_ID in the shell.
# S3_CREDENTIAL_CHAIN = "env;sso;config;process"
# S3_REGION = "us-east-1"   # optional override; else AWS_DEFAULT_REGION / AWS_REGION
# Long-running server with SSO: consider S3_REFRESH_AUTO = True
# S3_FORCE_CREDENTIAL_CHAIN = True  # use only DuckDB chain even if AWS_* env vars are set
#
# If you see "Secret Validation Failure" / "Credential Chain: 'config'", DuckDB validated too
# early. Defaults now use VALIDATION 'none' (credentials checked on first S3 read). For a strict
# check at startup, set: S3_CREDENTIAL_VALIDATION = "exists"
# If you use SSO / `aws login` or a named profile, start the app from a shell where AWS_PROFILE
# is set (scripts/start.sh does not load ~/.zshrc; IDEs need AWS_PROFILE in their run config).
#
# Option B — Static keys (or export AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN
# in the shell; those are picked up without putting them in this file).
#
# S3_ACCESS_KEY_ID = "..."
# S3_SECRET_ACCESS_KEY = "..."
# S3_REGION = "us-east-1"
