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
# 📂 Load Data
# -----------------------------
@st.cache_data
def load_data():
    return pd.read_csv("account_prioritisation_challenge_data.csv")

df = load_data()

# -----------------------------
# 🧠 Helpers
# -----------------------------
def get_column(df, col):
    if col in df.columns:
        return df[col]
    matches = difflib.get_close_matches(col, df.columns, n=1, cutoff=0.6)
    if matches:
        st.warning(f"Using '{matches[0]}' instead of '{col}'")
        return df[matches[0]]
    return pd.Series(0, index=df.index)

def normalize(series):
    series = pd.to_numeric(series, errors="coerce").fillna(0)
    return (series - series.min()) / (series.max() - series.min() + 1e-9)

def safe(x):
    try:
        return float(x)
    except:
        return 0.0

def r(x):
    return round(safe(x), 2)

# -----------------------------
# 🧮 Compute Scores
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
# Categorisation
# -----------------------------
def categorize(score):
    if score >= 75:
        return "High Priority"
    elif score >= 50:
        return "Growth Focus"
    elif score >= 30:
        return "Watchlist"
    else:
        return "Low Priority"

df["category"] = df["priority_score_norm"].apply(categorize)

# -----------------------------
# 🎛 Filters
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
# 📊 Summary
# -----------------------------
st.subheader("📊 Portfolio Summary")

col1, col2, col3 = st.columns(3)
col1.metric("Avg Priority", r(df_filtered["priority_score"].mean()))
col2.metric("Avg Normalized", r(df_filtered["priority_score_norm"].mean()))
col3.metric("High Priority Accounts", int((df_filtered["priority_score_norm"] > 70).sum()))

# -----------------------------
# 🏆 Category Blocks (Top 3 each)
# -----------------------------
st.subheader("🏆 Top Accounts by Category")

categories = ["High Priority", "Growth Focus", "Watchlist", "Low Priority"]

colors = {
    "High Priority": "#2ecc71",
    "Growth Focus": "#f1c40f",
    "Watchlist": "#e67e22",
    "Low Priority": "#95a5a6"
}

for cat in categories:
    st.markdown(f"### {cat}")

    cat_df = df_sorted[df_sorted["category"] == cat].head(3)

    if cat_df.empty:
        st.write("No accounts in this category")
        continue

    cols = st.columns(3)

    for i, (_, acc) in enumerate(cat_df.iterrows()):
        with cols[i]:
            size = max(50, min(int(acc.get("arr_gbp",0)/1e6), 100))

            st.markdown(
                f"""
                <div style="text-align:center;">
                    <div style="
                        width:{size}px;
                        height:{size}px;
                        background:{colors[cat]};
                        border-radius:50%;
                        margin:auto;">
                    </div>
                    <br>
                    <b>{acc['account_name']}</b><br>
                    Score: {r(acc['priority_score_norm'])}<br>
                    ARR: £{int(acc.get('arr_gbp',0))}
                </div>
                """,
                unsafe_allow_html=True
            )

# -----------------------------
# 🔍 Drill Down
# -----------------------------
st.subheader("🔍 Drill into Account")

selected_account = st.selectbox("Select Account", df_sorted["account_name"])
account = df_sorted[df_sorted["account_name"] == selected_account].iloc[0]

st.markdown(f"""
### 📌 Account Overview
- Region: {account.get('region')}
- Segment: {account.get('segment')}
- Industry: {account.get('industry')}
- ARR: £{r(account.get('arr_gbp'))}
""")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Priority", r(account["priority_score"]))
col2.metric("Risk", r(account["risk_score"]))
col3.metric("Growth", r(account["growth_score"]))
col4.metric("Engagement", r(account["attention_score"]))

# Supporting Evidence
st.subheader("🧠 Supporting Evidence")

metrics_list = [
    "revenue_trend",
    "usage_trend",
    "open_tickets_count",
    "sla_breaches_90d",
    "latest_nps"
]

evidence = pd.DataFrame({
    "Metric": [m.replace("_"," ").title() for m in metrics_list],
    "Value": [r(account.get(m,0)) for m in metrics_list]
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
