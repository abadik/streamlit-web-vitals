import streamlit as st
from pathlib import Path
from google.oauth2 import service_account
from google.cloud import bigquery
from pandas import DataFrame, to_datetime
from streamlit_authenticator import Authenticate

# Big Query
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"]
)
client = bigquery.Client(credentials=credentials)


@st.experimental_memo(ttl=3600)
def run_query(query):
    query_job = client.query(query)
    rows_raw = query_job.result()
    rows = [dict(row) for row in rows_raw]
    df = DataFrame.from_records(rows)
    try:
        df["date"] = to_datetime(df["date"])
        df = df.set_index("date")
    except:
        pass
    return df


# Authenticator
config = st.secrets["authorization"]
auth_credentials = {"usernames": {}}
for u in list(config["credentials"]["usernames"]):
    auth_credentials["usernames"][u["username"]] = dict(u)


def auth():
    return Authenticate(
        credentials=auth_credentials,
        cookie_name=config["cookie"]["name"],
        key=config["cookie"]["key"],
        cookie_expiry_days=config["cookie"]["expiry_days"],
    )


# Data Manipulation
def filter_web_vitals_data(
    df, *, date_from="", date_to="", domain="", url="", exact_url=False, metric=""
):
    if domain:
        df = df[df.domain == domain]
    if url:
        if exact_url:
            df = df[df.url == url]
        else:
            df = df[df.url.str.contains(url.lower(), regex=True)]
    if date_from:
        df = df[df.index.date >= date_from]
    if date_to:
        df = df[df.index.date <= date_to]
    if metric:
        df = df[df[metric].notnull()]
    return df


def filter_load_and_render_data(
    df, *, date_from="", date_to="", domain="", url="", exact_url=False
):
    if domain:
        df = df[df.domain == domain]
    if url:
        if exact_url:
            df = df[df.url == url]
        else:
            df = df[df.url.str.contains(url.lower(), regex=True)]
    if date_from:
        df = df[df.index.date >= date_from]
    if date_to:
        df = df[df.index.date <= date_to]
    return df


# Components
def read_html_component(filename):
    with open(Path(f"./components/{filename}.html"), "r", encoding="utf-8-sig") as f:
        return f.read()


# Helpers
def web_vital_metric_unit(metric):
    return " ms" if metric != "CLS" else ""


def web_vital_total_value(df, metric, *, quantile=0.75):
    if metric == "CLS":
        return "{0:.2f}".format(df[metric].quantile(quantile))
    else:
        return int(round(df[metric].quantile(quantile)))


def load_and_render_total_value(df, *, quantile=0.95):
    return (
        "{0:.1f}".format(df["page_load_time"].quantile(quantile)),
        "{0:.1f}".format(df["render_time"].quantile(quantile)),
    )
