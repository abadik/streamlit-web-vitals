import streamlit as st
from streamlit_authenticator import Authenticate
from google.oauth2 import service_account
from google.cloud import bigquery
from pandas import DataFrame

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


@st.experimental_memo(ttl=600)
def run_query(query):
    query_job = client.query(query)
    rows_raw = query_job.result()
    # Convert to list of dicts. Required for st.experimental_memo to hash the return value.
    rows = [dict(row) for row in rows_raw]
    return DataFrame.from_records(rows)


if authentication_status:
    # Print content
    authenticator.logout("Logout", "main")
    st.write("Output:")
    st.dataframe(run_query(queries["bq_web_vitals"]))

elif authentication_status == False:
    st.error("Username/password is incorrect")
elif authentication_status == None:
    st.warning("Please enter your username and password")
