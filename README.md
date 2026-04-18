# DataGov Crawler & DB Client — CSCE 2501

Python tools for **US catalog.data.gov** datasets: a **BeautifulSoup** crawler that populates **MySQL** (`DataGov_DB`), plus a **Streamlit** web client (**Milestone III**) for queries and transactions against a **remote** database (e.g. Aiven).

---

## Repository layout

| Path | Purpose |
|------|---------|
| `crawler.py` | Milestone II: crawl, parse, load MySQL, export CSVs |
| `milestone3_app/app.py` | Milestone III: Streamlit UI |
| `milestone3_app/db.py` | MySQL connection (TLS for remote hosts) |
| `milestone3_app/run_milestone3.sh` | Launcher script (optional) |
| `requirements.txt` | All Python dependencies (crawler + app) |
| `users.csv` | Seed users for `User` / `Usage` |
| `sql/` | Schema, optional migrations, `UserWithAge` view |

**Course deliverables not stored in Git:** full **SQL dumps** (often tens of MB) and **video** — submit those through the LMS / Drive as instructed. Keep dumps **out of this repo** (see `.gitignore`); generate them locally when needed.

---

## Requirements

- **Milestone II (crawler):** Python **3.9+** (3.11 recommended).
- **Milestone III (Streamlit):** Python **3.11+** (Streamlit and pandas 2.x do not install on 3.7).

```bash
cd DataGov_Crawler
python3.11 -m venv .venv311
source .venv311/bin/activate          # Windows: .venv311\Scripts\activate
pip install -U pip
pip install -r requirements.txt
```

---

## Milestone II — Crawler

Crawls catalog pages (`/dataset/?page=1` … `page=N`, default **100** pages × **20** datasets), parses dataset and organization pages, loads `Organization`, `Dataset`, tags, file formats, users from `users.csv`, and seeds **500** `Usage` rows. **Resume:** `processed_ids.txt` (gitignored). **Rate limit:** `REQUEST_DELAY_SEC` (default 1s).

### Crawler environment variables

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
| `EXPORT_CSV_DIR` | `export_csv` (empty = skip export) |
| `PROCESSED_IDS_FILE` | `processed_ids.txt` (empty = disable resume) |
| `ORG_CONTACT_MAX_LEN` | `45` (raise after optional `TEXT` migration) |

### Run crawler

```bash
export MYSQL_USER=your_user
export MYSQL_PASSWORD=your_password
python crawler.py
```

Dry run (no DB): `python crawler.py --dry-run`

Schema SQL: `sql/schema_datagov_db.sql`. Optional: `sql/alter_organization_contact_to_text.sql`, `sql/view_user_with_age.sql`.

---

## Milestone III — Streamlit app (remote MySQL)

The app must use your **hosted** database (e.g. **Aiven**), not only `localhost`, for the course demo.

### Environment variables

| Variable | Example (Aiven) |
|----------|------------------|
| `MYSQL_HOST` | `mysql-xxxxx.g.aivencloud.com` |
| `MYSQL_PORT` | `17976` |
| `MYSQL_USER` | `avnadmin` |
| `MYSQL_PASSWORD` | *(from Aiven; never commit)* |
| `MYSQL_DATABASE` | `DataGov_DB` |
| `MYSQL_SSL_CA` | `/full/path/to/ca.pem` |

**Local MySQL without TLS:** omit `MYSQL_SSL_CA` and set `MYSQL_SSL_DISABLED=true`.

### Run app (executable)

There is no separate `.exe`. After exports:

```bash
cd DataGov_Crawler
source .venv311/bin/activate
export MYSQL_HOST=... MYSQL_PORT=... MYSQL_USER=... MYSQL_PASSWORD=... MYSQL_DATABASE=DataGov_DB MYSQL_SSL_CA=/path/to/ca.pem
streamlit run milestone3_app/app.py
```

Or: `chmod +x milestone3_app/run_milestone3.sh` once, then `./milestone3_app/run_milestone3.sh` (same `export` lines first).

### Export a dump from Aiven (for submission)

```bash
mysqldump \
  -h YOUR_AIVEN_HOST -P YOUR_PORT -u avnadmin -p \
  --ssl-mode=VERIFY_CA --ssl-ca=/path/to/ca.pem \
  --single-transaction --routines --events --triggers \
  --set-gtid-purged=OFF \
  DataGov_DB > ~/DataGov_DB_aiven_milestone3.sql
```

Sanity check: `grep -m 1 "CREATE TABLE"` and `grep -m 1 "INSERT INTO"` on that file. **Store the file outside Git** or upload only to the course system.

---

## Schema notes

- `Organization.org_name` is `VARCHAR(45)`; the crawler stores the org **slug** as `org_name`. Optional `TEXT` migration for long contacts: `sql/alter_organization_contact_to_text.sql`.
- **Derived age:** `sql/view_user_with_age.sql` — base `User` table uses `birthdate` only.

---

## GitHub

Remote: configure `origin` and push `main` as usual. **Never commit** real passwords, `ca.pem` secrets, or large `DataGov_DB*.sql` dumps (see `.gitignore`).

## License

Course / educational use. Data.gov content follows [data.gov policies](https://data.gov/).
