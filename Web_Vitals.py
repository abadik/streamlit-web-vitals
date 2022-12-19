import streamlit as st
import altair as alt
from streamlit.components.v1 import html
from functions import (
    run_query,
    auth,
    filter_web_vitals_data,
    read_html_component,
    web_vital_metric_unit,
    web_vital_total_value,
    text_score,
)
from constants import metrics_data, web_vitals_quantile, favicon
from pandas import DataFrame


# Page Setup
st.set_page_config(page_title="wilio - Web Vitals", page_icon=favicon)

# Load Queries
queries = st.secrets["queries"]

# APP Auth
authenticator = auth()
name, authentication_status, username = authenticator.login("Login", "main")

# Constants
metrics = list(metrics_data.keys())

# Main Content
if authentication_status:
    authenticator.logout("Logout", "main")

    # Query Execute
    data = run_query(queries["bq_web_vitals"])

    # Options
    domains = sorted(list(data.domain.unique()))
    devices = sorted(list(data.device.unique()))

    # Title
    st.title("Web Vitals")

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
        url = st.text_input(label="URL:", value="", help="Type the whole or part of the URL.")
        exact_url = st.checkbox(label="Exact URL", value=False)
        device = st.multiselect(label="Device category:", options=devices, default=[])

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
            f'{metrics_data[metric]["first_breakpoint"]}{web_vital_metric_unit(metric)}',
            f'{metrics_data[metric]["second_breakpoint"]}{web_vital_metric_unit(metric)}',
        )
        html(html=breakpoints_html, height=104)
        page_type = st.multiselect(
            label="Page type:",
            options=sorted(
                list(data[(data.domain == domain) & (data[metric].notnull())].page_type.unique())
            ),
            default=[],
        )

    # Full Width Content
    # Filtered Data
    out = filter_web_vitals_data(
        df=data,
        url=url,
        exact_url=exact_url,
        date_from=date_from,
        date_to=date_to,
        domain=domain,
        metric=metric,
        devices=device,
        page_types=page_type,
    )

    # Slider
    percentile = st.select_slider(
        label="Percentile:",
        options=list(range(5, 105, 5)),
        value=web_vitals_quantile * 100,
    )

    # Line Chart
    chart_data = (
        out[metric]
        .groupby("date")
        .agg(func="quantile", q=percentile / 100, numeric_only=True)
        .reset_index()
    )
    line_chart = alt.Chart(chart_data).encode(
        alt.X(shorthand="date", title="Date"),
        alt.Y(shorthand=metric, title="Time (ms)" if metric != "CLS" else "Score"),
    )
    st.write(
        f"<center><b>{metric} ({web_vital_total_value(df=out,metric=metric, quantile=percentile/100)}{web_vital_metric_unit(metric)}) [{percentile}th percentile]</b></center>",
        unsafe_allow_html=True,
    )
    st.altair_chart(
        altair_chart=line_chart.mark_line(interpolate="basis")
        + line_chart.mark_point(filled=True, size=100),
        use_container_width=True,
    )

    value_counts = out["page_type"].value_counts()

    if len(page_type) == 1:
        top_number = 1
    else:
        top_number = st.select_slider(
            label="Top N:",
            options=list(range(1, len(list(value_counts)) + 1, 1)),
            value=min(5, len(list(value_counts))),
        )

    top_page_types = value_counts.index.tolist()[: min(top_number, len(list(value_counts)))] + [
        "other"
    ]
    t = {}
    for k, v in dict(value_counts).items():
        if k in top_page_types:
            t[k] = v
        else:
            try:
                t["other"] += v
            except:
                t["other"] = v

    pie = (
        alt.Chart(DataFrame([t], index=["value"]).transpose().reset_index())
        .encode(
            theta=alt.Theta("value:Q"),
            color=alt.Color("index:N", legend=alt.Legend(title="Page type")),
            tooltip=[
                alt.Tooltip("index:N", title="Page type"),
                alt.Tooltip("value:Q", title="Count"),
            ],
        )
        .mark_arc(innerRadius=50)
        .properties(title="Records by page type")
    )

    renamed_out = out.loc[:, ("page_type", metric)]
    renamed_out["page_type"] = [
        x if x in top_page_types else "other" for x in renamed_out.loc[:, ("page_type")]
    ]
    renamed_out["score"] = [text_score(x, metric) for x in renamed_out.loc[:, (metric)]]

    bar_chart = (
        alt.Chart(renamed_out)
        .transform_aggregate(count="count()", groupby=["score", "page_type"])
        .transform_joinaggregate(total="sum(count)", groupby=["page_type"])
        .transform_calculate(frac=alt.datum.count / alt.datum.total)
        .mark_bar()
        .encode(
            x=alt.X("page_type:O", title="Page type"),
            y=alt.Y("count:Q", stack="normalize", axis=alt.Axis(title="Percent", format="%")),
            color=alt.Color(
                "score:N",
                scale=alt.Scale(
                    range=["#0CCE6B", "#FFA400", "#FF4E42"],
                ),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("score:N", title="Score"),
                alt.Tooltip("count:Q", title="Total"),
                alt.Tooltip("frac:Q", title="Percentage", format=".0%"),
                alt.Tooltip("page_type:N", title="Page type"),
            ],
        )
    )

    col3, col4 = st.columns(spec=(1, 1), gap="medium")

    with col3:
        st.altair_chart(altair_chart=pie, use_container_width=True)
    with col4:
        st.altair_chart(altair_chart=bar_chart, use_container_width=True)

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
