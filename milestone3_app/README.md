# Milestone III — Web client (Streamlit)

## Prerequisites

- **Python 3.9+ required** (3.11 recommended). Streamlit and pandas 2.x do **not** install on Python 3.7.
- From the repo root, use a **venv** created with 3.11, then: `pip install -r requirements.txt`

Example:

```bash
cd /path/to/DataGov_Crawler
python3.11 -m venv .venv311
source .venv311/bin/activate
pip install -U pip
pip install -r requirements.txt
```

## Environment variables

| Variable | Example (Aiven) |
|----------|------------------|
| `MYSQL_HOST` | `mysql-xxxxx.g.aivencloud.com` |
| `MYSQL_PORT` | `17976` |
| `MYSQL_USER` | `avnadmin` |
| `MYSQL_PASSWORD` | (from Aiven console) |
| `MYSQL_DATABASE` | `DataGov_DB` |
| `MYSQL_SSL_CA` | `/full/path/to/ca.pem` |

For **local** MySQL without TLS, omit `MYSQL_SSL_CA` and set `MYSQL_SSL_DISABLED=true`.

## Run

**Executable (what to submit / demo):** after setting the `MYSQL_*` environment variables, start the app with either:

```bash
cd /path/to/DataGov_Crawler
source .venv311/bin/activate   # or your own 3.11+ venv
export MYSQL_HOST=... MYSQL_PORT=... MYSQL_USER=... MYSQL_PASSWORD=... MYSQL_DATABASE=DataGov_DB MYSQL_SSL_CA=/path/to/ca.pem
streamlit run milestone3_app/app.py
```

Or use the launcher (make it executable once: `chmod +x milestone3_app/run_milestone3.sh`):

```bash
cd /path/to/DataGov_Crawler
export MYSQL_HOST=...   # same as above
./milestone3_app/run_milestone3.sh
```

There is **no separate `.exe`** for Streamlit; the “executable” is **Streamlit + this entry command** (and your venv with `requirements.txt` installed).

The browser opens to the app; use the sidebar dropdown for each required feature.

## Course deliverables

- Source: this folder + shared `requirements.txt`
- **Executable:** the `streamlit run ...` command above (record it in your submission README)
- **Remote DB:** keep `MYSQL_HOST` pointed at Aiven (not `127.0.0.1`) for the demo video
- **Dump:** export from Aiven with `mysqldump` using the same SSL flags as import
