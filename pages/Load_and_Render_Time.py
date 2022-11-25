import streamlit as st
import altair as alt
from functions import (
    run_query,
    auth,
    read_html_component,
    filter_load_and_render_data,
    load_and_render_total_value,
)
from constants import load_and_render_time_quantile, favicon


# Page Setup
st.set_page_config(page_title="wilio - Page Load and Render Time", page_icon=favicon)

# Load Queries
queries = st.secrets["queries"]

# APP Auth
authenticator = auth()
name, authentication_status, username = authenticator.login("Login", "main")

# Main Content
if authentication_status:
    authenticator.logout("Logout", "main")

    # Query Execute
    data = run_query(queries["bq_load_and_render_time"])

    # Options
    domains = sorted(list(data.domain.unique()))

    # Title
    st.title("Load and Render Time")

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
        domain = st.selectbox(label="Domain:", options=tuple(domains), index=domains.index(".sk"))

    # Second Column
    with col2:
        date_to = st.date_input(
            label="Date to:",
            min_value=data.index.min(),
            max_value=data.index.max(),
            value=data.index.max(),
        )
        url = st.text_input(label="URL:", value="", help="Type the whole or part of the URL.")
        exact_url = st.checkbox(label="Exact URL", value=False)

    # Full Width Content

    # Slider
    percentile = st.select_slider(
        label="Percentile:",
        options=list(range(5, 105, 5)),
        value=load_and_render_time_quantile * 100,
    )

    # Filtered Data
    out = filter_load_and_render_data(
        df=data,
        url=url,
        exact_url=exact_url,
        date_from=date_from,
        date_to=date_to,
        domain=domain,
    )

    # Total Values
    total_load_time, total_render_time = load_and_render_total_value(out, quantile=percentile / 100)

    # Line Chart
    chart_data = (
        out[["page_load_time", "render_time"]]
        .rename(columns={"page_load_time": "Page Load Time", "render_time": "Render Time"})
        .groupby("date")
        .agg(func="quantile", q=percentile / 100, numeric_only=True)
        .reset_index()
        .melt("date")
    )
    line_chart = alt.Chart(chart_data).encode(
        alt.X(shorthand="date", title="Date"),
        alt.Y(shorthand="value", title="Time (s)"),
        alt.Color(
            shorthand="variable",
            title="",
        ),
    )
    st.write(
        f"<center><b>Page Load Time ({total_load_time} s) and Render Time ({total_render_time} s) [{percentile}th percentile]</b></center>",
        unsafe_allow_html=True,
    )
    st.altair_chart(
        altair_chart=line_chart.mark_line(interpolate="basis")
        + line_chart.mark_point(filled=True, size=100),
        use_container_width=True,
    )

    # Download Data
    st.download_button(
        label="Download data",
        data=out.reset_index(drop=True).to_csv().encode("utf-8-sig"),
        file_name="data.csv",
        mime="text/csv",
    )

    # Data Table
    st.dataframe(out.reset_index(drop=True))


elif authentication_status == False:
    st.error("Username/password is incorrect")
elif authentication_status == None:
    st.warning("Please enter your username and password")
