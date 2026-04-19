# DataGov Catalog — Database System (CSCE 2501)

This repository contains a Python **web crawler** that collects dataset metadata from [catalog.data.gov](https://catalog.data.gov/dataset/), loads it into a **MySQL** schema (`DataGov_DB`), and a **Streamlit** client application for interactive access to that database over a **remote** MySQL deployment.

---

## Contents

| Path | Description |
|------|-------------|
| `crawler.py` | Crawler: HTTP fetch, HTML parsing, database load, optional CSV export |
| `milestone3_app/app.py` | Client application (Streamlit) |
| `milestone3_app/db.py` | Database connection (TLS when `MYSQL_SSL_CA` is set) |
| `milestone3_app/run_milestone3.sh` | Optional launcher |
| `requirements.txt` | Python dependencies |
| `users.csv` | Input file for seeding the `User` table and random `Usage` rows |
| `sql/` | DDL scripts: base schema, optional `Organization.contact_information` alteration, `UserWithAge` view |

Large **SQL dump** files and the **demonstration recording** are not version-controlled; submit those according to the course instructions.

---

## Environment

- **Crawler:** Python 3.9 or newer (3.11 recommended).
- **Client application:** Python 3.11 or newer (required for the current Streamlit and pandas versions).

```bash
python3.11 -m venv .venv311
source .venv311/bin/activate
pip install -U pip
pip install -r requirements.txt
```

---

## Milestone II — Data population (`crawler.py`)

The crawler requests catalog listing pages (`/dataset/?page=1` … `page=N`, default 100 pages, 20 datasets per page), follows dataset detail pages and organization pages where available, and inserts into `Organization`, `Dataset`, `tag`, `Dataset_has_tag`, `FileFormat`, and the relationship table linking formats to datasets (schema-dependent). It loads rows from `users.csv` into `User` and inserts up to **500** random rows into `Usage`. Request spacing is controlled by `REQUEST_DELAY_SEC` (default 1 second). Completed dataset identifiers may be recorded in `processed_ids.txt` for resumable runs (file is listed in `.gitignore`).

### Variables (crawler)

| Variable | Default |
|----------|---------|
| `MYSQL_HOST` | `localhost` |
| `MYSQL_PORT` | `3306` |
| `MYSQL_USER` | `root` |
| `MYSQL_PASSWORD` | *(empty)* |
| `MYSQL_DATABASE` | `DataGov_DB` |
| `CRAWL_MAX_PAGES` | `100` |
| `REQUEST_DELAY_SEC` | `1.0` |
| `USERS_CSV` | `users.csv` |
| `EXPORT_CSV_DIR` | `export_csv` (empty string skips CSV export) |
| `PROCESSED_IDS_FILE` | `processed_ids.txt` (empty string disables resume) |
| `ORG_CONTACT_MAX_LEN` | `45` |

```bash
export MYSQL_USER=...
export MYSQL_PASSWORD=...
python crawler.py
```

Dry run (no database writes): `python crawler.py --dry-run`

Apply `sql/schema_datagov_db.sql` on the server before the first crawl. Optional scripts: `sql/alter_organization_contact_to_text.sql`, `sql/view_user_with_age.sql`.

---

## Milestone III — Application layer (`milestone3_app`)

The client connects to MySQL using the variables below. For providers that require TLS, set `MYSQL_SSL_CA` to the service CA certificate path.

### Variables (application)

| Variable | Description |
|----------|-------------|
| `MYSQL_HOST` | Server hostname |
| `MYSQL_PORT` | TCP port |
| `MYSQL_USER` | Account name |
| `MYSQL_PASSWORD` | Account password |
| `MYSQL_DATABASE` | Database name (e.g. `DataGov_DB`) |
| `MYSQL_SSL_CA` | Path to CA bundle (TLS) |
| `MYSQL_SSL_DISABLED` | Set to `true` only for local servers without TLS |

### Run

```bash
source .venv311/bin/activate
export MYSQL_HOST=... MYSQL_PORT=... MYSQL_USER=... MYSQL_PASSWORD=... MYSQL_DATABASE=DataGov_DB MYSQL_SSL_CA=/path/to/ca.pem
streamlit run milestone3_app/app.py
```

Optional: `chmod +x milestone3_app/run_milestone3.sh` then `./milestone3_app/run_milestone3.sh` after the same exports.

Streamlit is the runnable entry point (no separate compiled binary).

### Logical backup (`mysqldump`)

```bash
mysqldump -h HOST -P PORT -u USER -p \
  --ssl-mode=VERIFY_CA --ssl-ca=/path/to/ca.pem \
  --single-transaction --routines --events --triggers \
  --set-gtid-purged=OFF \
  DataGov_DB > DataGov_DB_backup.sql
```

---

## Schema notes

`Organization.org_name` is defined as `VARCHAR(45)` in the provided schema; the crawler stores a stable organization key compatible with that length. Longer contact strings may be stored fully if `sql/alter_organization_contact_to_text.sql` is applied and `ORG_CONTACT_MAX_LEN` is increased accordingly.

The `User` table stores `birthdate`; derived age can be exposed through `sql/view_user_with_age.sql`.

---

## License

Educational use. Dataset listings originate from [data.gov](https://data.gov/); refer to their terms of use.
