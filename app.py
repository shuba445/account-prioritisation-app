import streamlit as st
import pandas as pd
import numpy as np
import difflib

# -----------------------------
# Load Data
# -----------------------------
@st.cache_data
def load_data():
    df = pd.read_csv("account_prioritisation_challenge_data.csv")
    return df

df = load_data()

# -----------------------------
# Compute Scores (Safe)
# -----------------------------
def normalize(series):
    return (series - series.min()) / (series.max() - series.min() + 1e-9)

def compute_scores(df):
    df = df.copy()
    def safe_col(df, col):
        return df[col] if col in df.columns else pd.Series(0, index=df.index)

    df["revenue_trend"] = (safe_col(df,"mrr_current_gbp") - safe_col(df,"mrr_3_months_ago_gbp")) / (safe_col(df,"mrr_3_months_ago_gbp")+1)
    df["usage_trend"] = (safe_col(df,"usage_current") - safe_col(df,"usage_previous")) / (safe_col(df,"usage_previous")+1)
    df["support_score"] = normalize(safe_col(df,"open_tickets") + safe_col(df,"sla_breaches")*2)
    df["nps_score"] = 1 - normalize(safe_col(df,"nps"))
    df["risk_score"] = (normalize(-df["revenue_trend"])*0.25 + normalize(-df["usage_trend"])*0.25 + df["support_score"]*0.25 + df["nps_score"]*0.25)*100
    df["growth_score"] = (normalize(safe_col(df,"expansion_pipeline"))*0.4 + normalize(safe_col(df,"seat_utilisation"))*0.2 + normalize(df["usage_trend"])*0.2 + normalize(safe_col(df,"positive_sales_signal"))*0.2)*100
    df["attention_score"] = (normalize(safe_col(df,"arr"))*0.4 + normalize(safe_col(df,"days_since_last_contact"))*0.3 + df["support_score"]*0.3)*100
    # Priority
    df["metric1"] = df["risk_score"]
    df["metric2"] = df["growth_score"]
    df["priority_score"] = df["metric1"]*0.5 + df["metric2"]*0.5 + df["attention_score"]*0.2
    return df

df = compute_scores(df)
df_sorted = df.sort_values(by="priority_score", ascending=False)

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Account Prioritisation Dashboard", layout="wide")

st.title("📊 Account Prioritisation Dashboard")

# Top Accounts Cards
st.subheader("🏆 Top Accounts to Focus On")
top_accounts = df_sorted.head(5)

cols = st.columns(5)
for i, (_, account) in enumerate(top_accounts.iterrows()):
    with cols[i]:
        st.metric(label=account["account_name"], value=f"{account['priority_score']:.1f}")
        st.progress(min(account['priority_score']/100, 1.0))  # visual progress bar

st.markdown("---")

# Portfolio Table with sortable metrics
st.subheader("📈 Full Portfolio Overview")
st.dataframe(
    df_sorted[["account_name","priority_score","risk_score","growth_score","attention_score"]],
    use_container_width=True
)

# Drill Down Section
st.subheader("🔍 Account Details")
selected_account = st.selectbox("Select Account", df_sorted["account_name"])
account = df_sorted[df_sorted["account_name"]==selected_account].iloc[0]

# Metrics in columns
col1, col2, col3, col4 = st.columns(4)
col1.metric("Priority", f"{account['priority_score']:.1f}")
col2.metric("Risk", f"{account['risk_score']:.1f}")
col3.metric("Growth", f"{account['growth_score']:.1f}")
col4.metric("Attention", f"{account['attention_score']:.1f}")

# Progress bars for each metric
st.subheader("Metric Breakdown")
st.progress(min(account['risk_score']/100, 1.0))
st.progress(min(account['growth_score']/100, 1.0))
st.progress(min(account['attention_score']/100, 1.0))

# Expandable Details
with st.expander("View detailed metrics"):
    st.write({
        "Revenue Trend": account["revenue_trend"],
        "Usage Trend": account["usage_trend"],
        "Open Tickets": account["open_tickets"],
        "NPS": account["nps"]
    })

# Recommended Actions
st.subheader("✅ Recommended Actions")
actions = []
if account["risk_score"] > 60: actions.append("🚨 Immediate outreach")
if account["support_score"] > 0.5: actions.append("🛠 Resolve support issues")
if account["growth_score"] > 50: actions.append("📈 Explore upsell")
if not actions: actions.append("👀 Monitor account")

for a in actions:
    st.write(f"- {a}")
