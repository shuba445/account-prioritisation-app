import streamlit as st
import pandas as pd
import numpy as np
import difflib
import os

# -----------------------------
# 🔐 Authentication
# -----------------------------
def login():
    st.title("🔐 Account Prioritisation Tool")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username == "admin" and password == "demo":
            st.session_state["logged_in"] = True
        else:
            st.error("Invalid credentials")

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login()
    st.stop()

# -----------------------------
# Load Data
# -----------------------------
@st.cache_data
def load_data():
    return pd.read_csv("account_prioritisation_challenge_data.csv")

df = load_data()

# -----------------------------
# Helper functions
# -----------------------------
def get_column(df, col):
    if col in df.columns:
        return df[col]
    matches = difflib.get_close_matches(col, df.columns, n=1, cutoff=0.6)
    if matches:
        return df[matches[0]]
    return pd.Series(0, index=df.index)

def normalize(series):
    series = pd.to_numeric(series, errors="coerce").fillna(0)
    return (series - series.min()) / (series.max() - series.min() + 1e-9)

def safe_float(x):
    try:
        if pd.isna(x):
            return 0.0
        return float(x)
    except:
        return 0.0

def r(x):
    return round(safe_float(x), 2)

# -----------------------------
# Compute Scores
# -----------------------------
def compute_scores(df):
    df = df.copy()

    df["revenue_trend"] = (
        (get_column(df,"mrr_current_gbp") - get_column(df,"mrr_3m_ago_gbp")) /
        (get_column(df,"mrr_3m_ago_gbp")+1)
    )

    df["usage_trend"] = (
        (get_column(df,"usage_score_current") - get_column(df,"usage_score_3m_ago")) /
        (get_column(df,"usage_score_3m_ago")+1)
    )

    df["support_score"] = normalize(
        get_column(df,"open_tickets_count") +
        get_column(df,"sla_breaches_90d")*2
    )

    df["nps_score"] = 1 - normalize(get_column(df,"latest_nps"))

    df["positive_sales_signal"] = normalize(
        get_column(df,"open_leads_count") +
        get_column(df,"avg_lead_score")
    )

    df["days_since_last_contact"] = (
        pd.to_datetime("today") -
        pd.to_datetime(get_column(df,"latest_note_date"), errors="coerce")
    ).dt.days.fillna(0)

    df["risk_score"] = (
        normalize(-df["revenue_trend"])*0.25 +
        normalize(-df["usage_trend"])*0.25 +
        df["support_score"]*0.25 +
        df["nps_score"]*0.25
    ) * 100

    df["growth_score"] = (
        normalize(get_column(df,"expansion_pipeline_gbp"))*0.4 +
        normalize(get_column(df,"seats_used"))*0.2 +
        normalize(df["usage_trend"])*0.2 +
        normalize(df["positive_sales_signal"])*0.2
    ) * 100

    df["attention_score"] = (
        normalize(get_column(df,"arr_gbp"))*0.4 +
        normalize(df["days_since_last_contact"])*0.3 +
        df["support_score"]*0.3
    ) * 100

    df["priority_score"] = (
        df["risk_score"]*0.5 +
        df["growth_score"]*0.5 +
        df["attention_score"]*0.2
    )

    return df

df = compute_scores(df)

# -----------------------------
# Normalize within segment
# -----------------------------
df["priority_score_norm"] = df.groupby("segment")["priority_score"].transform(
    lambda x: (x - x.min()) / (x.max() - x.min() + 1e-9) * 100
)

# -----------------------------
# Filters
# -----------------------------
st.set_page_config(layout="wide")
st.title("📊 Account Prioritisation Dashboard")

segment = st.selectbox("Segment", ["All"] + list(df["segment"].dropna().unique()))
region = st.selectbox("Region", ["All"] + list(df["region"].dropna().unique()))
industry = st.selectbox("Industry", ["All"] + list(df["industry"].dropna().unique()))

df_filtered = df.copy()
if segment != "All":
    df_filtered = df_filtered[df_filtered["segment"] == segment]
if region != "All":
    df_filtered = df_filtered[df_filtered["region"] == region]
if industry != "All":
    df_filtered = df_filtered[df_filtered["industry"] == industry]

df_sorted = df_filtered.sort_values(by="priority_score", ascending=False)

# -----------------------------
# BCG MATRIX (FIXED + INTERACTIVE)
# -----------------------------
st.subheader("📊 Account Heatmap (BCG Matrix)")

st.markdown("""
**X-axis → Growth Score**  
**Y-axis → Risk Score**
""")

st.markdown(
    "<div style='position:relative; height:450px; border:2px solid #ccc;'>",
    unsafe_allow_html=True
)

selected_from_chart = None

for _, acc in df_sorted.iterrows():

    x = safe_float(acc["growth_score"]) / 100
    y = safe_float(acc["risk_score"]) / 100

    left = int(max(0, min(x, 1)) * 90)
    bottom = int(max(0, min(y, 1)) * 90)

    # Quadrant color
    if x > 0.5 and y > 0.5:
        color = "#2ecc71"
        label = "Stable Growth"
    elif x <= 0.5 and y > 0.5:
        color = "#e74c3c"
        label = "At Risk"
    elif x > 0.5 and y <= 0.5:
        color = "#f1c40f"
        label = "Emerging"
    else:
        color = "#95a5a6"
        label = "Low Priority"

    size = max(12, min(int(safe_float(acc["arr_gbp"]) / 1e6), 40))

    tooltip = f"""
    {acc['account_name']}
    Priority: {r(acc['priority_score'])}
    Growth: {r(acc['growth_score'])}
    Risk: {r(acc['risk_score'])}
    ARR: {int(safe_float(acc['arr_gbp']))}
    Segment: {acc.get('segment')}
    """

    st.markdown(
        f"""
        <div title="{tooltip}"
        onclick="window.parent.postMessage({{'account':'{acc['account_name']}'}} , '*')"
        style="
            position:absolute;
            left:{left}%;
            bottom:{bottom}%;
            width:{size}px;
            height:{size}px;
            background:{color};
            border-radius:50%;
            opacity:0.75;
            cursor:pointer;">
        </div>
        """,
        unsafe_allow_html=True
    )

# Axis labels
st.markdown("""
<div style='position:absolute; left:5px; bottom:5px;'>Low Growth</div>
<div style='position:absolute; right:5px; bottom:5px;'>High Growth</div>
<div style='position:absolute; left:5px; top:5px;'>High Risk</div>
<div style='position:absolute; left:5px; bottom:50%; transform:rotate(-90deg);'>Risk ↑</div>
""", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# Drill Down (Selectable)
# -----------------------------
st.subheader("🔍 Drill into Account")

selected_account = st.selectbox(
    "Select Account",
    df_sorted["account_name"]
)

account = df_sorted[df_sorted["account_name"] == selected_account].iloc[0]

# Executive Overview
st.markdown(f"""
### 📌 Account Overview
- **Region:** {account.get('region')}
- **Segment:** {account.get('segment')}
- **Industry:** {account.get('industry')}
- **Owner:** {account.get('account_owner')}
- **ARR:** £{r(account.get('arr_gbp'))}
""")

# Metrics
col1, col2, col3, col4 = st.columns(4)
col1.metric("Priority", r(account["priority_score"]))
col2.metric("Risk", r(account["risk_score"]))
col3.metric("Growth", r(account["growth_score"]))
col4.metric("Engagement", r(account["attention_score"]))

# Supporting Evidence
st.subheader("🧠 Supporting Evidence")

evidence = pd.DataFrame({
    "Metric": ["Revenue Trend","Usage Trend","Open Tickets","NPS"],
    "Value": [
        r(account["revenue_trend"]),
        r(account["usage_trend"]),
        r(account.get("open_tickets_count",0)),
        r(account.get("latest_nps",0))
    ]
})

st.table(evidence)

# Actions
st.subheader("✅ Recommended Actions")

actions = []
if account["risk_score"] > 60:
    actions.append("🚨 Immediate outreach")
if account["growth_score"] > 50:
    actions.append("📈 Upsell opportunity")
if not actions:
    actions.append("👀 Monitor")

for a in actions:
    st.write(a)

# Notes
st.subheader("💾 Notes")

note = st.text_area("Add notes")

if st.button("Save"):
    file = "notes.csv"
    if os.path.exists(file):
        ndf = pd.read_csv(file)
    else:
        ndf = pd.DataFrame(columns=["account","note"])

    ndf = pd.concat([ndf, pd.DataFrame([{
        "account": selected_account,
        "note": note
    }])])

    ndf.to_csv(file, index=False)
    st.success("Saved")
