#!/usr/bin/env python3
"""
Crawl catalog.data.gov (first N pages), parse with BeautifulSoup, populate DataGov_DB.

Environment variables (optional defaults in parentheses):
  MYSQL_HOST (localhost)
  MYSQL_PORT (3306)
  MYSQL_USER (root)
  MYSQL_PASSWORD (empty)
  MYSQL_DATABASE (DataGov_DB)
  REQUEST_DELAY_SEC (1.0)   — delay after each HTTP request
  CRAWL_MAX_PAGES (100)     — catalog pages to fetch
  USERS_CSV (users.csv)
  EXPORT_CSV_DIR (export_csv) — set empty to skip CSV export after crawl
  PROCESSED_IDS_FILE (processed_ids.txt) — set empty to disable resume checkpointing
  ORG_CONTACT_MAX_LEN (45) — raise to 65535 after sql/alter_organization_contact_to_text.sql

Also supports CKAN-style identifiers in dataset URLs: /dataset/<id>
"""

from __future__ import annotations

import csv
import hashlib
import os
import random
import re
import sys
import time
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import mysql.connector
import requests
from bs4 import BeautifulSoup
from mysql.connector import errorcode

BASE = "https://catalog.data.gov"
CATALOG_PATH = "/dataset/"
USER_AGENT = (
    "Mozilla/5.0 (compatible; DataGovCrawler/1.0; +https://data.gov; academic research)"
)


def env_float(name: str, default: float) -> float:
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    return float(v)


def env_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    return int(v)


def env_str(name: str, default: str) -> str:
    v = os.environ.get(name)
    return default if v is None else v


def org_contact_max_len() -> int:
    return env_int("ORG_CONTACT_MAX_LEN", 45)


def resume_ids_path() -> str | None:
    p = env_str("PROCESSED_IDS_FILE", "processed_ids.txt").strip()
    return p if p else None


def load_processed_ids(path: str) -> set[str]:
    ids: set[str] = set()
    if not os.path.isfile(path):
        return ids
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                ids.add(line)
    return ids


def append_processed_id(path: str, dataset_id: str) -> None:
    with open(path, "a", encoding="utf-8") as fa:
        fa.write(dataset_id + "\n")
        fa.flush()
        try:
            os.fsync(fa.fileno())
        except OSError:
            pass


def sleep_polite() -> None:
    time.sleep(env_float("REQUEST_DELAY_SEC", 1.0))


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
    return s


def fetch(sess: requests.Session, url: str) -> str | None:
    try:
        r = sess.get(url, timeout=60)
        r.raise_for_status()
        return r.text
    except requests.RequestException as e:
        print(f"[warn] GET failed {url}: {e}", file=sys.stderr)
        return None
    finally:
        sleep_polite()


def normalize_download_url(url: str) -> str:
    url = (url or "").strip()
    if url.startswith("https:///"):
        return "https://" + url[len("https:///") :]
    if url.startswith("http:///"):
        return "http://" + url[len("http:///") :]
    return url


def clip(s: str | None, max_len: int) -> str | None:
    if s is None:
        return None
    s = s.strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def map_org_type(raw: str | None) -> str:
    """Map data.gov organization-type hint to schema ENUM."""
    if not raw:
        return "Other"
    r = raw.lower().strip()
    if r == "federal":
        return "Federal"
    if r == "state":
        return "State"
    if r == "city":
        return "City"
    if r in ("county", "local", "regional", "tribal"):
        return "Local"
    return "Other"


def parse_date_us(s: str | None) -> datetime | None:
    if not s:
        return None
    s = re.sub(r"<[^>]+>", "", s)
    s = " ".join(s.split())
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def parse_catalog_listing(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict[str, Any]] = []
    for li in soup.select("li.dataset-item"):
        h3 = li.select_one("h3.dataset-heading a")
        if not h3 or not h3.get("href"):
            continue
        href = h3["href"].strip()
        if not href.startswith("/dataset/"):
            continue
        path = href.rstrip("/").split("/")
        # /dataset/foo or /dataset/group/foo — take last segment as slug id
        identifier = path[-1] if path else ""
        if not identifier or identifier == "dataset":
            continue
        name = h3.get_text(strip=True)
        org_el = li.select_one("p.dataset-organization")
        org_display = ""
        if org_el:
            org_display = org_el.get_text(" ", strip=True)
            org_display = re.sub(r"\s*[—–-]\s*$", "", org_display).strip()
        org_type_span = li.select_one("[data-organization-type]")
        list_org_type = (
            org_type_span.get("data-organization-type")
            if org_type_span
            else None
        )
        resources: list[tuple[str | None, str]] = []
        for a in li.select("ul.dataset-resources a[data-format]"):
            fmt = (a.get("data-format") or "").upper() or None
            u = normalize_download_url(urljoin(BASE, a.get("href", "")))
            if u:
                resources.append((fmt, u))
        out.append(
            {
                "identifier": identifier,
                "dataset_name": name,
                "org_display_list": org_display,
                "list_org_type": list_org_type,
                "list_resources": resources,
                "detail_path": href,
            }
        )
    return out


def _organization_slug_from_href(href: str) -> str | None:
    href = (href or "").strip()
    if "?" in href:
        return None
    path = href.split("?")[0].rstrip("/")
    if path in ("/organization", ""):
        return None
    if not path.startswith("/organization/"):
        return None
    slug = path.split("/")[-1]
    return slug if slug and slug != "organization" else None


def _organization_link_from_soup(soup: BeautifulSoup) -> tuple[str | None, str | None]:
    """Resolve org slug from breadcrumb, aside, or other /organization/&lt;slug&gt; links."""
    candidates: list[tuple[str, str | None]] = []
    selectors = (
        'div[role="main"] ol.breadcrumb a[href^="/organization/"]',
        'aside.secondary a[href^="/organization/"]',
        'aside a[href^="/organization/"]',
    )
    for sel in selectors:
        for a in soup.select(sel):
            slug = _organization_slug_from_href(a.get("href") or "")
            if not slug:
                continue
            display = a.get_text(strip=True) or None
            img = a.select_one("img")
            if (not display or len(display) < 2) and img and img.get("alt"):
                display = img.get("alt")
            candidates.append((slug, display))
    if not candidates:
        return None, None
    for slug, display in reversed(candidates):
        if display and len(display) > 1 and not display.lower().startswith("default "):
            return slug, display
    return candidates[-1][0], candidates[-1][1]


def _dataset_page_contact_fallback(soup: BeautifulSoup) -> str | None:
    """
    Contact when org profile is missing or thin: Data.gov puts a Contact block
    on many dataset pages (mailto / phone text). Also picks up obvious
    'contact publisher' style links in the sidebar if present.
    """
    sec = soup.select_one("section.module-narrow.contact") or soup.select_one(
        "aside section.contact"
    )
    if sec:
        t = sec.get_text("\n", strip=True)
        if t:
            return t
    aside = soup.select_one("aside.secondary") or soup.select_one("aside")
    if aside:
        for a in aside.select("a[href^='mailto:']"):
            label = a.get_text(" ", strip=True)
            href = (a.get("href") or "").strip()
            if label and href:
                return f"{label} ({href})"
            if href:
                return href
        for a in aside.select("a[href]"):
            text = a.get_text(" ", strip=True).lower()
            title = (a.get("title") or "").lower()
            if ("contact" in text and "publisher" in text) or (
                "contact" in title and "publisher" in title
            ):
                return a.get_text(" ", strip=True) or a.get("href")
    return None


def _access_level_from_soup(soup: BeautifulSoup) -> str:
    span = soup.select_one("#access-use span.access-public, #access-use span.access-restricted")
    if span:
        t = span.get_text(" ", strip=True)
        if "restricted" in t.lower() or "non-public" in t.lower():
            return clip("Restricted", 50) or "Restricted"
        if "public" in t.lower():
            return clip("Public", 50) or "Public"
        return clip(t[:80], 50) or "unknown"
    val = _additional_metadata_value(soup, "Public Access Level")
    if val:
        return clip(val, 50) or "unknown"
    return "unknown"


def _additional_metadata_value(soup: BeautifulSoup, label: str) -> str | None:
    section = soup.select_one("section.additional-info") or soup
    for th in section.select("th.dataset-label"):
        if th.get_text(strip=True).lower() == label.lower():
            td = th.find_next_sibling("td")
            if td:
                return td.get_text(" ", strip=True)
    return None


def _table_row_by_label(soup: BeautifulSoup, label: str) -> str | None:
    for th in soup.select("th.dataset-label"):
        if th.get_text(strip=True).lower() == label.lower():
            td = th.find_next_sibling("td")
            if td:
                return td.get_text(" ", strip=True)
    return None


def parse_dataset_detail(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one('article.module[itemscope][itemtype*="Dataset"]') or soup
    name_el = article.select_one("h1[itemprop=name]") or article.select_one("h1")
    dataset_name = name_el.get_text(strip=True) if name_el else None
    desc_el = article.select_one("div[itemprop=description].notes")
    description = None
    if desc_el:
        description = desc_el.get_text("\n", strip=True)

    license_text = None
    lic = article.select_one("#access-use")
    if lic:
        for strong in lic.find_all("strong"):
            if strong.get_text(strip=True).startswith("License"):
                parent = strong.parent
                if parent:
                    license_text = parent.get_text(" ", strip=True)
                    license_text = re.sub(
                        r"^License:\s*", "", license_text, flags=re.I
                    ).strip()
                break

    meta_created = parse_date_us(_table_row_by_label(article, "Metadata Created Date"))
    meta_updated = parse_date_us(_table_row_by_label(article, "Metadata Updated Date"))

    publisher = _table_row_by_label(article, "Publisher")
    maintainer = _table_row_by_label(article, "Maintainer")

    topic = (
        _additional_metadata_value(soup, "Theme")
        or _additional_metadata_value(soup, "Topic")
        or _additional_metadata_value(soup, "Category")
    )

    tags: list[str] = []
    for a in article.select("section.tags ul.tag-list a.tag"):
        t = a.get_text(strip=True)
        if t:
            tags.append(t)

    org_slug, org_display = _organization_link_from_soup(soup)
    sidebar_contact = _dataset_page_contact_fallback(soup)

    resources: list[tuple[str | None, str]] = []
    for li in article.select("li.resource-item"):
        fmt = None
        lbl = li.select_one("[data-format]")
        if lbl and lbl.get("data-format"):
            fmt = lbl.get("data-format").upper()
        dl = li.select_one("a.btn-primary[href]")
        if dl and dl.get("href"):
            u = normalize_download_url(urljoin(BASE, dl["href"]))
            if u:
                resources.append((fmt, u))
                continue
        cu = li.select_one('a[itemprop="contentUrl"][href]')
        if cu and cu.get("href"):
            u = normalize_download_url(urljoin(BASE, cu["href"]))
            if u:
                resources.append((fmt, u))

    return {
        "dataset_name": dataset_name,
        "description": description,
        "access_level": _access_level_from_soup(soup),
        "license": license_text,
        "metadata_creation_date": meta_created,
        "metadata_update_date": meta_updated,
        "publisher": publisher,
        "maintainer": maintainer,
        "topic": topic,
        "tags": tags,
        "org_slug": org_slug,
        "org_display_detail": org_display,
        "sidebar_contact": sidebar_contact,
        "detail_resources": resources,
    }


def parse_organization_page(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    info = soup.select_one("#organization-info .module-content") or soup.select_one(
        ".context-info .module-content"
    )
    org_type = None
    display_name = None
    description = None
    contact = None
    if info:
        ot = info.select_one("[data-organization-type]")
        if ot:
            org_type = ot.get("data-organization-type")
        h1 = info.select_one("h1.heading")
        if h1:
            display_name = h1.get_text(strip=True)
        for p in info.find_all("p"):
            cls = p.get("class") or []
            if "empty" in cls:
                continue
            txt = p.get_text("\n", strip=True)
            if txt:
                description = txt
                break
    if not display_name:
        h = soup.select_one("#content h1.heading") or soup.select_one("h1.heading")
        if h:
            display_name = h.get_text(strip=True)
    contact_sec = soup.select_one("section.module-narrow.contact .module-content")
    if contact_sec:
        contact = contact_sec.get_text(" ", strip=True)
    if not contact:
        fb = _dataset_page_contact_fallback(soup)
        if fb:
            contact = fb
    return {
        "org_type": org_type,
        "display_name": display_name,
        "description": description,
        "contact_information": contact,
    }


def synthetic_org_slug(display_name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", display_name.lower()).strip("-")[:36]
    if not base:
        base = "org"
    h = hashlib.sha1(display_name.encode("utf-8")).hexdigest()[:8]
    s = f"{base}-{h}"
    return s[:45]


def connect_db():
    cfg = {
        "host": os.environ.get("MYSQL_HOST", "localhost"),
        "port": env_int("MYSQL_PORT", 3306),
        "user": os.environ.get("MYSQL_USER", "root"),
        "password": os.environ.get("MYSQL_PASSWORD", ""),
        "database": os.environ.get("MYSQL_DATABASE", "DataGov_DB"),
        "charset": "utf8",
        "use_unicode": True,
    }
    return mysql.connector.connect(**cfg)


def ensure_organization(
    cur,
    org_name: str,
    org_type: str,
    description: str | None,
    contact: str | None,
) -> None:
    cur.execute(
        "SELECT org_name FROM Organization WHERE org_name = %s", (org_name,)
    )
    if cur.fetchone():
        return
    cur.execute(
        """
        INSERT INTO Organization (org_name, org_type, description, contact_information)
        VALUES (%s, %s, %s, %s)
        """,
        (
            org_name,
            org_type,
            clip(description, 65535),
            clip(contact, org_contact_max_len()),
        ),
    )


def upsert_dataset(cur, row: dict[str, Any], org_name: str) -> None:
    cur.execute(
        """
        INSERT INTO Dataset (
            identifier, dataset_name, description, access_level, license,
            metadata_creation_date, metadata_update_date, publisher, maintainer,
            topic, Organization_org_name
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON DUPLICATE KEY UPDATE
            dataset_name = VALUES(dataset_name),
            description = VALUES(description),
            access_level = VALUES(access_level),
            license = VALUES(license),
            metadata_creation_date = VALUES(metadata_creation_date),
            metadata_update_date = VALUES(metadata_update_date),
            publisher = VALUES(publisher),
            maintainer = VALUES(maintainer),
            topic = VALUES(topic),
            Organization_org_name = VALUES(Organization_org_name)
        """,
        (
            row["identifier"],
            clip(row["dataset_name"], 255),
            row.get("description"),
            clip(row["access_level"], 50) or "unknown",
            clip(row.get("license"), 100),
            row.get("metadata_creation_date"),
            row.get("metadata_update_date"),
            clip(row.get("publisher"), 45),
            clip(row.get("maintainer"), 45),
            clip(row.get("topic"), 100),
            org_name,
        ),
    )


def ensure_tag(cur, tag_name: str) -> None:
    cur.execute("INSERT IGNORE INTO tag (tag_name) VALUES (%s)", (tag_name,))


def link_dataset_tag(cur, dataset_id: str, tag_name: str) -> None:
    cur.execute(
        """
        INSERT IGNORE INTO Dataset_has_tag (Dataset_identifier, tag_tag_name)
        VALUES (%s, %s)
        """,
        (dataset_id, tag_name),
    )


def get_or_create_file_format(cur, fmt: str | None, url: str) -> int:
    url = clip(url, 512) or ""
    cur.execute("SELECT format_id FROM FileFormat WHERE url = %s", (url,))
    r = cur.fetchone()
    if r:
        return int(r[0])
    cur.execute(
        "INSERT INTO FileFormat (format_type, url) VALUES (%s, %s)",
        (clip(fmt, 45), url),
    )
    return int(cur.lastrowid)


def link_file_dataset(cur, format_id: int, dataset_id: str) -> None:
    cur.execute(
        """
        INSERT IGNORE INTO FileFormat_has_Dataset (FileFormat_format_id, Dataset_identifier)
        VALUES (%s, %s)
        """,
        (format_id, dataset_id),
    )


def load_users(cur, path: str) -> list[str]:
    emails: list[str] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            email = (row.get("email") or "").strip()
            if not email:
                continue
            username = clip(row.get("username"), 45) or email.split("@")[0][:45]
            gender = clip(row.get("gender"), 45)
            birth = row.get("birthdate") or None
            country = clip(row.get("country"), 45)
            cur.execute("SELECT email FROM User WHERE email = %s", (email,))
            if not cur.fetchone():
                cur.execute(
                    """
                    INSERT INTO User (email, username, gender, birthdate, country)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (email, username, gender, birth, country),
                )
            emails.append(email)
    return emails


def seed_usage(cur, user_emails: list[str], dataset_ids: list[str], n: int = 500) -> None:
    if not user_emails or not dataset_ids:
        return
    cats = ("analytics", "machine learning", "field research")
    cur.execute("SELECT COUNT(*) FROM Usage")
    start = cur.fetchone()[0]
    if start >= n:
        return
    need = n - start
    projects = ("Course project", "Research", "Policy analysis", "Dashboard", "Thesis")
    for _ in range(need):
        cur.execute(
            """
            INSERT INTO Usage (project_name, project_category, User_email, Dataset_identifier)
            VALUES (%s, %s, %s, %s)
            """,
            (
                random.choice(projects),
                random.choice(cats),
                random.choice(user_emails),
                random.choice(dataset_ids),
            ),
        )


def export_table_csv(cur, table: str, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    cur.execute(f"SELECT * FROM `{table}`")
    rows = cur.fetchall()
    colnames = [d[0] for d in cur.description] if cur.description else []
    path = os.path.join(out_dir, f"{table}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(colnames)
        for row in rows:
            w.writerow(row)
    print(f"[export] {path} ({len(rows)} rows)")


def run_crawl(populate_db: bool = True) -> None:
    max_pages = env_int("CRAWL_MAX_PAGES", 100)
    resume_path = resume_ids_path()
    processed: set[str] = load_processed_ids(resume_path) if resume_path else set()
    if resume_path and processed:
        print(
            f"[resume] skipping {len(processed)} dataset(s) listed in {resume_path}",
            flush=True,
        )
    sess = session()
    listings: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        url = f"{BASE}{CATALOG_PATH}?page={page}"
        print(f"[catalog] page {page}/{max_pages}", flush=True)
        html = fetch(sess, url)
        if not html:
            continue
        items = parse_catalog_listing(html)
        if not items:
            print(f"[warn] no datasets on page {page}", file=sys.stderr)
        listings.extend(items)

    print(f"[catalog] total listing rows: {len(listings)}", flush=True)

    org_cache: dict[str, dict[str, Any]] = {}
    merged: list[dict[str, Any]] = []

    for i, item in enumerate(listings):
        ds_id = item["identifier"]
        if ds_id in processed:
            continue
        org_slug: str | None = None
        from_breadcrumb = False
        detail_url = urljoin(BASE, item["detail_path"])
        print(
            f"[detail] ({i+1}/{len(listings)}) {ds_id}",
            flush=True,
        )
        html = fetch(sess, detail_url)
        detail = parse_dataset_detail(html) if html else {}
        if detail.get("org_slug"):
            org_slug = detail["org_slug"]
            from_breadcrumb = True
        org_display = detail.get("org_display_detail") or item.get(
            "org_display_list", ""
        )
        if not org_slug and org_display:
            org_slug = synthetic_org_slug(org_display)

        if org_slug and org_slug not in org_cache:
            if from_breadcrumb:
                org_url = f"{BASE}/organization/{org_slug}"
                ohtml = fetch(sess, org_url)
                org_cache[org_slug] = (
                    parse_organization_page(ohtml) if ohtml else {}
                )
            else:
                org_cache[org_slug] = {}

        oinfo = org_cache.get(org_slug, {}) if org_slug else {}
        org_type = map_org_type(
            oinfo.get("org_type") or item.get("list_org_type")
        )
        display = (
            oinfo.get("display_name")
            or org_display
            or org_slug
            or "Unknown"
        )
        desc_parts = []
        if display and display != org_slug:
            desc_parts.append(display)
        if oinfo.get("description"):
            desc_parts.append(oinfo["description"])
        org_description = "\n\n".join(desc_parts) if desc_parts else None

        org_name_key = clip(org_slug, 45) or synthetic_org_slug(display or "org")

        resources = list(detail.get("detail_resources") or [])
        seen_u = {u for _, u in resources}
        for fmt, u in item.get("list_resources") or []:
            if u not in seen_u:
                resources.append((fmt, u))
                seen_u.add(u)

        contact = oinfo.get("contact_information") or detail.get("sidebar_contact")

        row = {
            "identifier": item["identifier"],
            "dataset_name": detail.get("dataset_name") or item["dataset_name"],
            "description": detail.get("description"),
            "access_level": detail.get("access_level") or "unknown",
            "license": detail.get("license"),
            "metadata_creation_date": detail.get("metadata_creation_date"),
            "metadata_update_date": detail.get("metadata_update_date"),
            "publisher": detail.get("publisher"),
            "maintainer": detail.get("maintainer"),
            "topic": detail.get("topic"),
            "tags": detail.get("tags") or [],
            "resources": resources,
            "_org_name_key": org_name_key,
            "_org_type": org_type,
            "_org_description": org_description,
            "_contact": contact,
        }
        merged.append(row)

    if not populate_db:
        print("[dry-run] skipping database writes")
        return

    try:
        conn = connect_db()
    except mysql.connector.Error as e:
        if e.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print(
                "[error] MySQL access denied — check MYSQL_USER / MYSQL_PASSWORD",
                file=sys.stderr,
            )
        elif e.errno == errorcode.ER_BAD_DB_ERROR:
            print(
                "[error] Database missing — create DataGov_DB first",
                file=sys.stderr,
            )
        else:
            print(f"[error] MySQL: {e}", file=sys.stderr)
        sys.exit(1)

    cur = conn.cursor()
    try:
        seen_orgs: set[str] = set()

        def flush_one_dataset(row: dict[str, Any]) -> None:
            oname = row["_org_name_key"]
            if oname not in seen_orgs:
                ensure_organization(
                    cur,
                    oname,
                    row["_org_type"],
                    row["_org_description"],
                    row["_contact"],
                )
                seen_orgs.add(oname)
            upsert_dataset(cur, row, row["_org_name_key"])
            for tag in row["tags"]:
                t = clip(tag, 100)
                if not t:
                    continue
                ensure_tag(cur, t)
                link_dataset_tag(cur, row["identifier"], t)
            for fmt, url in row["resources"]:
                if not url:
                    continue
                fid = get_or_create_file_format(cur, fmt, url)
                link_file_dataset(cur, fid, row["identifier"])

        use_checkpoint = bool(resume_path)
        for row in merged:
            flush_one_dataset(row)
            if use_checkpoint:
                conn.commit()
                append_processed_id(resume_path, row["identifier"])
        if not use_checkpoint:
            conn.commit()
        print(
            "[db] commit OK"
            + (" (per-dataset checkpoint)" if use_checkpoint else ""),
            flush=True,
        )

        users_path = os.environ.get("USERS_CSV", "users.csv")
        if os.path.isfile(users_path):
            user_emails = load_users(cur, users_path)
            cur.execute("SELECT identifier FROM Dataset")
            ids = [r[0] for r in cur.fetchall()]
            seed_usage(cur, user_emails, ids, 500)
            conn.commit()
        else:
            print(f"[warn] users file not found: {users_path}", file=sys.stderr)

        export_dir = os.environ.get("EXPORT_CSV_DIR", "export_csv")
        if export_dir:
            for t in (
                "Organization",
                "Dataset",
                "tag",
                "Dataset_has_tag",
                "FileFormat",
                "FileFormat_has_Dataset",
                "User",
                "Usage",
            ):
                export_table_csv(cur, t, export_dir)
    finally:
        cur.close()
        conn.close()


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in ("--dry-run", "-n"):
        run_crawl(populate_db=False)
    else:
        run_crawl(populate_db=True)


if __name__ == "__main__":
    main()
