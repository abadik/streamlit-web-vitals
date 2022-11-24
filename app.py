import streamlit as st
from streamlit_authenticator import Authenticate
from google.oauth2 import service_account
from google.cloud import bigquery
from pandas import DataFrame, to_datetime
from pathlib import Path
import altair as alt

# Queries
queries = st.secrets["queries"]
# App auth
config = st.secrets["authorization"]

authenticator = Authenticate(
    credentials=dict(config["credentials"]),
    cookie_name=config["cookie"]["name"],
    key=config["cookie"]["key"],
    cookie_expiry_days=config["cookie"]["expiry_days"],
)

name, authentication_status, username = authenticator.login("Login", "main")

# BQ API client
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"]
)
client = bigquery.Client(credentials=credentials)

metrics_data = dict(
    CLS=dict(first_breakpoint=0.1, second_breakpoint=0.25),
    FCP=dict(first_breakpoint=1800, second_breakpoint=3000),
    FID=dict(first_breakpoint=100, second_breakpoint=300),
    INP=dict(first_breakpoint=200, second_breakpoint=500),
    LCP=dict(first_breakpoint=2500, second_breakpoint=4000),
    TTFB=dict(first_breakpoint=800, second_breakpoint=1800),
)

metrics = list(metrics_data.keys())


@st.experimental_memo(ttl=6000)
def run_query(query):
    query_job = client.query(query)
    rows_raw = query_job.result()
    # Convert to list of dicts. Required for st.experimental_memo to hash the return value.
    rows = [dict(row) for row in rows_raw]
    df = DataFrame.from_records(rows)
    try:
        df["date"] = to_datetime(df["date"])
        df = df.set_index("date")
    except:
        pass
    try:
        for m in metrics:
            if m != "CLS":
                df[m] = df[m].astype(int)
    except:
        pass
    return df


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


if authentication_status:
    # Print content
    authenticator.logout("Logout", "main")
    data = run_query(queries["bq_web_vitals"])

    col1, padding, col2 = st.columns((12, 1, 12))

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
            f'{metrics_data[metric]["first_breakpoint"]}{" ms" if metric != "CLS" else ""}',
            f'{metrics_data[metric]["second_breakpoint"]}{" ms" if metric != "CLS" else ""}',
        )
        st.components.v1.html(html=breakpoints_html, height=100)

    out = filter_data(
        df=data,
        url=url,
        exact_url=exact_url,
        date_from=date_from,
        date_to=date_to,
        domain=domain,
        metric=metric,
    )

    chart_data = (
        out[metric].groupby("date").agg(func="quantile", q=0.75, numeric_only=True).reset_index()
    )
    line_chart = (
        alt.Chart(chart_data)
        .mark_line(interpolate="basis")
        .encode(
            alt.X("date", title="Date"), alt.Y(metric, title="ms" if metric != "CLS" else "score")
        )
        .properties(title=metric)
    )

    st.altair_chart(altair_chart=line_chart, use_container_width=True)

    show_columns = [x for x in list(out.columns) if not x in metrics or metrics.remove(x)] + [
        metric
    ]
    st.download_button(
        label="Download data",
        data=out[show_columns].reset_index(drop=True).to_csv().encode("utf-8-sig"),
        file_name="data.csv",
        mime="text/csv",
    )
    st.dataframe(out[show_columns].reset_index(drop=True))

elif authentication_status == False:
    st.error("Username/password is incorrect")
elif authentication_status == None:
    st.warning("Please enter your username and password")
