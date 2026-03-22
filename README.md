# Data.gov Catalog Crawler

Python crawler for [catalog.data.gov](https://catalog.data.gov/dataset/) that parses HTML with **BeautifulSoup**, loads results into **MySQL** (`DataGov_DB`), and exports table dumps as CSV. Built for **CSCE 2501 — Milestone II** (database population from Data.gov).

## Features

- Crawls catalog listing pages (`/dataset/?page=1` … `page=N`, default **100** pages, **20** datasets per page).
- For each dataset: fetches the detail page and (when available) the **organization** profile page from the breadcrumb.
- Extracts identifiers, names, organizations, access level, license, metadata dates, publisher, maintainer, topic (when present), tags, and file formats with download URLs.
- Inserts into `Organization`, `Dataset`, `tag`, `Dataset_has_tag`, `FileFormat`, and `FileFormat_has_Dataset` (organizations are **skipped if they already exist**).
- Loads users from `users.csv` and seeds up to **500** random `Usage` rows.
- **Polite crawling:** configurable delay after **each** HTTP request (default **1 second**).
- **Resume / checkpoint:** optional `processed_ids.txt` skips already-imported datasets and commits **per dataset** so a dropped connection does not force a full re-crawl.
- **Organization & contact fallbacks:** org slug is resolved from breadcrumb **or** sidebar links; contact text is taken from the org profile when possible, otherwise from the dataset page **Contact** block (mailto / phone) or obvious “contact publisher” sidebar links.

## Requirements

- Python 3.9+ recommended (3.7+ may work with the pinned dependencies).
- MySQL server with schema **`DataGov_DB`** already created (see your course SQL script).

## Setup

```bash
cd DataGov_Crawler
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create the database and tables in MySQL (your Milestone I script), then set connection variables if needed:

| Variable | Default |
|----------|---------|
| `MYSQL_HOST` | `localhost` |
| `MYSQL_PORT` | `3306` |
| `MYSQL_USER` | `root` |
| `MYSQL_PASSWORD` | *(empty)* |
| `MYSQL_DATABASE` | `DataGov_DB` |

## Usage

**Full crawl** (100 catalog pages, populate DB, write CSVs under `export_csv/`):

```bash
export MYSQL_USER=your_user
export MYSQL_PASSWORD=your_password
python crawler.py
```

**Dry run** (no database; checks parsing and network only):

```bash
python crawler.py --dry-run
```

**Faster local testing** (fewer pages, no delay):

```bash
CRAWL_MAX_PAGES=2 REQUEST_DELAY_SEC=0 python crawler.py --dry-run
```

### Optional environment variables

| Variable | Description |
|----------|-------------|
| `CRAWL_MAX_PAGES` | Number of catalog pages (default `100`). |
| `REQUEST_DELAY_SEC` | Seconds to sleep after each HTTP request (default `1.0`). |
| `USERS_CSV` | Path to users CSV (default `users.csv`). |
| `EXPORT_CSV_DIR` | Directory for exported table CSVs (default `export_csv`). Set to empty to skip export. |
| `PROCESSED_IDS_FILE` | Path to checkpoint file (default `processed_ids.txt`). Set to **empty** to disable resume. The file is gitignored. |
| `ORG_CONTACT_MAX_LEN` | Max length stored for `Organization.contact_information` (default `45`, matching the original schema). After applying `sql/alter_organization_contact_to_text.sql`, set e.g. `65535`. |

### Resume after an interrupted crawl

1. Leave `PROCESSED_IDS_FILE` at its default (or point it to your own path).
2. Re-run `python crawler.py`. Identifiers already listed in the file are **not** fetched again; each newly stored dataset is appended to the file after a successful DB commit.
3. For a **full** re-import from scratch, delete `processed_ids.txt` (and truncate or drop populated tables if you need a clean DB).

`Usage` seeding uses **all** rows in `Dataset` after the crawl, not only the current batch.

## Project layout

| File | Purpose |
|------|---------|
| `crawler.py` | Main crawler and DB loader |
| `requirements.txt` | Python dependencies |
| `users.csv` | Sample users for `User` / `Usage` seeding |
| `sql/alter_organization_contact_to_text.sql` | **Optional** migration: widen `contact_information` to `TEXT` |

## Schema note

`Organization.org_name` is limited to **45** characters in the provided schema. The crawler stores the organization **URL slug** (e.g. `exim-gov`) as `org_name` and keeps the full display name in `Organization.description` when available.

`Organization.contact_information` as `VARCHAR(45)` truncates long mailto lines or URLs. If your instructor allows a small schema change, run the optional SQL migration above and set `ORG_CONTACT_MAX_LEN` accordingly so contact data is preserved.

## Rationale (Milestone feedback)

These ideas align well with a production-style crawler:

- **Richer org / contact extraction** — Required by the project (“about” pages) and brittle in the wild; fallbacks on the dataset page reduce empty `Organization` rows.
- **Resume checkpoints** — Essential for long runs (100 pages + 2,000 detail requests + delays). The file-based list is simple to inspect and delete when you need a full reset.
- **TEXT for contact** — Good data modeling; keep the original `VARCHAR(45)` if the rubric forbids DDL changes, otherwise prefer `TEXT` plus a higher `ORG_CONTACT_MAX_LEN`.

## Remote repository

This folder is a **Git** repository. To publish it (for example on GitHub):

1. Create a **new empty** repository on GitHub (no README/license there if you want a clean history).
2. From this directory:

```bash
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git branch -M main
git push -u origin main
```

Do not commit real database passwords; use environment variables or a local `.env` file that stays **untracked** (`.env` is listed in `.gitignore`).

## License

Course / educational use. Data.gov content is subject to [data.gov policies](https://data.gov/).
