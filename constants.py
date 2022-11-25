import streamlit as st

metrics_data = dict(
    CLS=dict(first_breakpoint=0.1, second_breakpoint=0.25),
    FCP=dict(first_breakpoint=1800, second_breakpoint=3000),
    FID=dict(first_breakpoint=100, second_breakpoint=300),
    INP=dict(first_breakpoint=200, second_breakpoint=500),
    LCP=dict(first_breakpoint=2500, second_breakpoint=4000),
    TTFB=dict(first_breakpoint=800, second_breakpoint=1800),
)

web_vitals_quantile = 0.75

load_and_render_time_quantile = 0.95