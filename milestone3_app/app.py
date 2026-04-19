"""Streamlit front-end for the DataGov_DB MySQL application."""

from __future__ import annotations

import sys
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

import datetime as dt
from typing import Any, Optional

import mysql.connector
import pandas as pd
import streamlit as st

from db import connect, fileformat_has_dataset_column


def _conn():
    if "db_conn" not in st.session_state:
        st.session_state.db_conn = connect()
    else:
        try:
            if st.session_state.db_conn.is_connected():
                st.session_state.db_conn.ping(reconnect=True, attempts=2, delay=0.5)
            else:
                st.session_state.db_conn = connect()
        except Exception:
            try:
                st.session_state.db_conn.close()
            except Exception:
                pass
            st.session_state.db_conn = connect()
    return st.session_state.db_conn


def _run_query(sql: str, params: Optional[tuple[Any, ...]] = None) -> pd.DataFrame:
    conn = _conn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params or ())
        rows = cur.fetchall()
    finally:
        cur.close()
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _execute(sql: str, params: tuple[Any, ...]) -> None:
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
    finally:
        cur.close()


def _fileformat_join_fragment(weak: bool) -> str:
    if weak:
        return """
        JOIN FileFormat ff ON ff.Dataset_identifier = d.identifier
        """
    return """
        JOIN FileFormat_has_Dataset fhd ON fhd.Dataset_identifier = d.identifier
        JOIN FileFormat ff ON ff.format_id = fhd.FileFormat_format_id
        """


def main() -> None:
    st.set_page_config(page_title="DataGov DB Client", layout="wide")
    st.title("DataGov Database Client")
    st.caption("Database settings are read from `MYSQL_*` environment variables.")

    with st.sidebar:
        st.subheader("Connection")
        st.text(f"Host: {__import__('os').environ.get('MYSQL_HOST', '(default 127.0.0.1)')}")
        st.text(f"DB: {__import__('os').environ.get('MYSQL_DATABASE', 'DataGov_DB')}")
        ssl_ca = __import__('os').environ.get("MYSQL_SSL_CA", "")
        st.text("SSL CA: set" if ssl_ca else "SSL CA: (not set)")
        if st.button("Reconnect"):
            if "db_conn" in st.session_state:
                try:
                    st.session_state.db_conn.close()
                except Exception:
                    pass
                del st.session_state.db_conn
            st.rerun()

    try:
        weak_ff = False
        c = _conn().cursor()
        try:
            weak_ff = fileformat_has_dataset_column(c)
        finally:
            c.close()
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        st.stop()

    menu = st.selectbox(
        "Choose action",
        [
            "Register a user",
            "Add usage for a dataset",
            "View my usage",
            "Datasets by organization type",
            "Top 5 organizations by dataset count",
            "Datasets by file format",
            "Datasets by tag",
            "Totals: datasets by org / topic / format / org type",
            "Top 5 datasets by distinct users",
            "Usage distribution by project type",
            "Top 10 tags per project type",
        ],
    )

    if menu == "Register a user":
        st.subheader("Register a user")
        with st.form("reg"):
            email = st.text_input("Email (primary key)")
            username = st.text_input("Username (unique)")
            gender = st.text_input("Gender (optional)")
            birth_raw = st.text_input("Birthdate YYYY-MM-DD (optional)", "")
            country = st.text_input("Country (optional)")
            submitted = st.form_submit_button("Register")
        if submitted:
            if not email or not username:
                st.warning("Email and username are required.")
            else:
                bd: Optional[dt.date] = None
                parse_ok = True
                if birth_raw.strip():
                    try:
                        bd = dt.datetime.strptime(birth_raw.strip(), "%Y-%m-%d").date()
                    except ValueError:
                        st.error("Birthdate must be YYYY-MM-DD.")
                        parse_ok = False
                if parse_ok:
                    try:
                        _execute(
                            """
                            INSERT INTO `User` (email, username, gender, birthdate, country)
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (
                                email.strip(),
                                username.strip(),
                                gender.strip() or None,
                                bd,
                                country.strip() or None,
                            ),
                        )
                        st.success("User registered.")
                    except mysql.connector.Error as err:
                        st.error(str(err))

    elif menu == "Add usage for a dataset":
        st.subheader("Add usage")
        with st.form("usage"):
            email = st.text_input("User email")
            dataset_id = st.text_input("Dataset identifier")
            project = st.text_input("Project name (optional)")
            cat = st.selectbox(
                "Project category",
                ["analytics", "machine learning", "field research"],
            )
            submitted = st.form_submit_button("Add usage")
        if submitted:
            if not email or not dataset_id:
                st.warning("Email and dataset identifier are required.")
            else:
                try:
                    _execute(
                        """
                        INSERT INTO `Usage` (project_name, project_category, User_email, Dataset_identifier)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (project.strip() or None, cat, email.strip(), dataset_id.strip()),
                    )
                    st.success("Usage recorded.")
                except mysql.connector.Error as err:
                    st.error(str(err))

    elif menu == "View my usage":
        st.subheader("Usage for a user")
        email = st.text_input("User email", key="usage_email")
        if st.button("Load usage") and email.strip():
            df = _run_query(
                """
                SELECT u.usage_id, u.project_name, u.project_category, u.Dataset_identifier,
                       d.dataset_name, d.Organization_org_name
                FROM `Usage` u
                JOIN Dataset d ON d.identifier = u.Dataset_identifier
                WHERE u.User_email = %s
                ORDER BY u.usage_id DESC
                """,
                (email.strip(),),
            )
            st.dataframe(df, use_container_width=True)

    elif menu == "Datasets by organization type":
        st.subheader("Datasets filtered by organization type")
        org_type = st.selectbox("Organization type", ["Federal", "State", "City", "Local", "Other"])
        if st.button("Search"):
            df = _run_query(
                """
                SELECT d.identifier, d.dataset_name, d.topic, d.access_level, d.Organization_org_name
                FROM Dataset d
                JOIN Organization o ON o.org_name = d.Organization_org_name
                WHERE o.org_type = %s
                ORDER BY d.dataset_name
                LIMIT 500
                """,
                (org_type,),
            )
            st.dataframe(df, use_container_width=True)
            st.caption("Results limited to 500 rows.")

    elif menu == "Top 5 organizations by dataset count":
        st.subheader("Top 5 contributing organizations")
        df = _run_query(
            """
            SELECT d.Organization_org_name AS organization, COUNT(*) AS dataset_count
            FROM Dataset d
            GROUP BY d.Organization_org_name
            ORDER BY dataset_count DESC
            LIMIT 5
            """
        )
        st.dataframe(df, use_container_width=True)

    elif menu == "Datasets by file format":
        st.subheader("Datasets that offer a format (matches format_type substring)")
        fmt = st.text_input('Format keyword (e.g. "CSV", "JSON", "ZIP")', value="CSV")
        if st.button("Search formats"):
            join_sql = _fileformat_join_fragment(weak_ff)
            df = _run_query(
                f"""
                SELECT DISTINCT d.identifier, d.dataset_name, d.Organization_org_name, ff.format_type, ff.url
                FROM Dataset d
                {join_sql}
                WHERE ff.format_type LIKE %s
                ORDER BY d.dataset_name
                LIMIT 500
                """,
                (f"%{fmt.strip()}%",),
            )
            st.dataframe(df, use_container_width=True)

    elif menu == "Datasets by tag":
        st.subheader("Datasets with a given tag")
        tag = st.text_input("Tag name (exact match on stored tag)")
        if st.button("Search tags") and tag.strip():
            df = _run_query(
                """
                SELECT d.identifier, d.dataset_name, d.Organization_org_name, dht.tag_tag_name AS tag
                FROM Dataset d
                JOIN Dataset_has_tag dht ON dht.Dataset_identifier = d.identifier
                WHERE dht.tag_tag_name = %s
                ORDER BY d.dataset_name
                LIMIT 500
                """,
                (tag.strip(),),
            )
            st.dataframe(df, use_container_width=True)

    elif menu == "Totals: datasets by org / topic / format / org type":
        st.subheader("Aggregated dataset counts")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**By organization** (all publishers)")
            st.dataframe(
                _run_query(
                    """
                    SELECT Organization_org_name AS organization, COUNT(*) AS datasets
                    FROM Dataset
                    GROUP BY Organization_org_name
                    ORDER BY datasets DESC
                    """
                ),
                use_container_width=True,
                height=300,
            )
        with c2:
            st.markdown("**By topic**")
            st.dataframe(
                _run_query(
                    """
                    SELECT COALESCE(NULLIF(TRIM(topic), ''), '(no topic)') AS topic, COUNT(*) AS datasets
                    FROM Dataset
                    GROUP BY COALESCE(NULLIF(TRIM(topic), ''), '(no topic)')
                    ORDER BY datasets DESC
                    """
                ),
                use_container_width=True,
                height=300,
            )

        c3, c4 = st.columns(2)
        join_sql = _fileformat_join_fragment(weak_ff)
        with c3:
            st.markdown("**By file format** (distinct datasets)")
            st.dataframe(
                _run_query(
                    f"""
                    SELECT COALESCE(NULLIF(TRIM(ff.format_type), ''), '(unknown)') AS format_type,
                           COUNT(DISTINCT d.identifier) AS datasets
                    FROM Dataset d
                    {join_sql}
                    GROUP BY COALESCE(NULLIF(TRIM(ff.format_type), ''), '(unknown)')
                    ORDER BY datasets DESC
                    """
                ),
                use_container_width=True,
                height=300,
            )
        with c4:
            st.markdown("**By organization type**")
            st.dataframe(
                _run_query(
                    """
                    SELECT o.org_type, COUNT(*) AS datasets
                    FROM Dataset d
                    JOIN Organization o ON o.org_name = d.Organization_org_name
                    GROUP BY o.org_type
                    ORDER BY datasets DESC
                    """
                ),
                use_container_width=True,
                height=300,
            )

    elif menu == "Top 5 datasets by distinct users":
        st.subheader("Most-used datasets (distinct users in Usage)")
        df = _run_query(
            """
            SELECT u.Dataset_identifier, COUNT(DISTINCT u.User_email) AS distinct_users
            FROM `Usage` u
            GROUP BY u.Dataset_identifier
            ORDER BY distinct_users DESC
            LIMIT 5
            """
        )
        if not df.empty:
            ids = tuple(df["Dataset_identifier"].tolist())
            placeholders = ",".join(["%s"] * len(ids))
            names = _run_query(
                f"SELECT identifier, dataset_name FROM Dataset WHERE identifier IN ({placeholders})",
                ids,
            )
            merged = df.merge(names, left_on="Dataset_identifier", right_on="identifier", how="left")
            merged = merged.drop(columns=["identifier"], errors="ignore")
            st.dataframe(merged, use_container_width=True)
        else:
            st.dataframe(df, use_container_width=True)

    elif menu == "Usage distribution by project type":
        st.subheader("Usage rows by project_category")
        df = _run_query(
            """
            SELECT project_category, COUNT(*) AS usage_rows
            FROM `Usage`
            GROUP BY project_category
            ORDER BY usage_rows DESC
            """
        )
        st.dataframe(df, use_container_width=True)
        if not df.empty:
            st.bar_chart(df.set_index("project_category"))

    elif menu == "Top 10 tags per project type":
        st.subheader("Top 10 tags co-occurring with usage, per project type")
        df = _run_query(
            """
            WITH tag_counts AS (
                SELECT
                    u.project_category,
                    dht.tag_tag_name AS tag_name,
                    COUNT(*) AS tag_weight
                FROM `Usage` u
                JOIN Dataset_has_tag dht ON dht.Dataset_identifier = u.Dataset_identifier
                GROUP BY u.project_category, dht.tag_tag_name
            ),
            ranked AS (
                SELECT
                    project_category,
                    tag_name,
                    tag_weight,
                    ROW_NUMBER() OVER (
                        PARTITION BY project_category
                        ORDER BY tag_weight DESC, tag_name ASC
                    ) AS rn
                FROM tag_counts
            )
            SELECT project_category, tag_name, tag_weight
            FROM ranked
            WHERE rn <= 10
            ORDER BY project_category, rn
            """
        )
        st.dataframe(df, use_container_width=True)


if __name__ == "__main__":
    main()
