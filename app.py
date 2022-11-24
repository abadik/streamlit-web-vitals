import streamlit as st
from streamlit_authenticator import Authenticate
from google.oauth2 import service_account
from google.cloud import bigquery
from pandas import DataFrame, to_datetime
from pathlib import Path
import altair as alt
from streamlit.components.v1 import html

# Load Queries
queries = st.secrets["queries"]

# APP Auth
config = st.secrets["authorization"]
auth_credentials = {"usernames": {}}
for u in list(config["credentials"]["usernames"]):
    auth_credentials["usernames"][u["username"]] = dict(u)


authenticator = Authenticate(
    credentials=auth_credentials,
    cookie_name=config["cookie"]["name"],
    key=config["cookie"]["key"],
    cookie_expiry_days=config["cookie"]["expiry_days"],
)

name, authentication_status, username = authenticator.login("Login", "main")

# BQ API Client and Query Execute
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


# Constants
metrics_data = dict(
    CLS=dict(first_breakpoint=0.1, second_breakpoint=0.25),
    FCP=dict(first_breakpoint=1800, second_breakpoint=3000),
    FID=dict(first_breakpoint=100, second_breakpoint=300),
    INP=dict(first_breakpoint=200, second_breakpoint=500),
    LCP=dict(first_breakpoint=2500, second_breakpoint=4000),
    TTFB=dict(first_breakpoint=800, second_breakpoint=1800),
)

metrics = list(metrics_data.keys())

# Helpers
def filter_data(df, *, date_from="", date_to="", domain="", url="", exact_url=False, metric=""):
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


def read_html_component(filename):
    with open(Path(f"./components/{filename}.html"), "r", encoding="utf-8-sig") as f:
        return f.read()


def metric_unit(metric):
    return " ms" if metric != "CLS" else ""


def total_value(df, metric):
    if metric == "CLS":
        return "{0:.2f}".format(df[metric].quantile(0.75))
    else:
        return int(round(df[metric].quantile(0.75)))


# Main Content
if authentication_status:
    authenticator.logout("Logout", "main")

    # Query Execute
    data = run_query(queries["bq_web_vitals"])

    # Columns
    col1, col2 = st.columns(spec=(1, 1), gap="medium")

    # First Column
    with col1:
        date_from = st.date_input(
            label="Date from:",
            min_value=data.index.min(),
            max_value=data.index.max(),
            value=data.index.min(),
        )
        domain = st.selectbox(label="Domain:", options=tuple(data.domain.unique()))
        url = st.text_input(label="URL:", value="", help="Type the whole or part of the URL.")
        exact_url = st.checkbox(label="Exact URL", value=False)

    # Second Column
    with col2:
        date_to = st.date_input(
            label="Date to:",
            min_value=data.index.min(),
            max_value=data.index.max(),
            value=data.index.max(),
        )
        metric = st.selectbox(label="Metric:", options=tuple(metrics), index=1)
        breakpoints_html = read_html_component("breakpoints").format(
            metric,
            "decimal number (score)" if metric == "CLS" else "miliseconds (ms)",
            f'{metrics_data[metric]["first_breakpoint"]}{metric_unit(metric)}',
            f'{metrics_data[metric]["second_breakpoint"]}{metric_unit(metric)}',
        )
        html(html=breakpoints_html, height=100)

    # Full Width Content
    # Filtered Data
    out = filter_data(
        df=data,
        url=url,
        exact_url=exact_url,
        date_from=date_from,
        date_to=date_to,
        domain=domain,
        metric=metric,
    )

    # Line Chart
    chart_data = (
        out[metric].groupby("date").agg(func="quantile", q=0.75, numeric_only=True).reset_index()
    )
    line_chart = (
        alt.Chart(chart_data)
        .mark_line(interpolate="basis")
        .encode(
            alt.X(shorthand="date", title="Date"),
            alt.Y(shorthand=metric, title="ms" if metric != "CLS" else "score"),
        )
        .properties(
            title=f"{metric} (75th quantile) - total: {total_value(df=out,metric=metric)}{metric_unit(metric)}"
        )
    )
    st.altair_chart(altair_chart=line_chart, use_container_width=True)

    # Download Data
    show_columns = [x for x in list(out.columns) if not x in metrics or metrics.remove(x)] + [
        metric
    ]
    st.download_button(
        label="Download data",
        data=out[show_columns].reset_index(drop=True).to_csv().encode("utf-8-sig"),
        file_name="data.csv",
        mime="text/csv",
    )

    # Data Table
    st.dataframe(out[show_columns].reset_index(drop=True))

elif authentication_status == False:
    st.error("Username/password is incorrect")
elif authentication_status == None:
    st.warning("Please enter your username and password")
