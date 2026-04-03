import streamlit as st
import pandas as pd
import numpy as np
import difflib
import os
from datetime import datetime

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
    df = pd.read_csv("account_prioritisation_challenge_data.csv")
    return df

df = load_data()

# -----------------------------
# Column helper
# -----------------------------
def get_column(df, expected_col):
    if expected_col in df.columns:
        return df[expected_col]
    else:
        matches = difflib.get_close_matches(expected_col, df.columns, n=1, cutoff=0.6)
        if matches:
            st.warning(f"Column '{expected_col}' not found. Using '{matches[0]}' instead.")
            return df[matches[0]]
        else:
            return pd.Series(0, index=df.index)

# -----------------------------
# Feature Engineering
# -----------------------------
def normalize(series):
    if series.empty:
        return pd.Series(0, index=series.index)
    return (series - series.min()) / (series.max() - series.min() + 1e-9)

def compute_scores(df):
    df = df.copy()
    # Revenue & Usage
    df["revenue_trend"] = (get_column(df,"mrr_current_gbp") - get_column(df,"mrr_3m_ago_gbp")) / (get_column(df,"mrr_3m_ago_gbp")+1)
    df["usage_trend"] = (get_column(df,"usage_score_current") - get_column(df,"usage_score_3m_ago")) / (get_column(df,"usage_score_3m_ago")+1)
    # Support & NPS
    df["support_score"] = normalize(get_column(df,"open_tickets_count") + get_column(df,"sla_breaches_90d")*2)
    df["nps_score"] = 1 - normalize(get_column(df,"latest_nps"))
    # Risk
    df["risk_score"] = (
        normalize(-df["revenue_trend"])*0.25 +
        normalize(-df["usage_trend"])*0.25 +
        df["support_score"]*0.25 +
        df["nps_score"]*0.25
    ) * 100
    # Growth
    df["growth_score"] = (
        normalize(get_column(df,"expansion_pipeline_gbp"))*0.4 +
        normalize(get_column(df,"seats_used")/get_column(df,"seats_purchased"))*0.2 +
        normalize(df["usage_trend"])*0.2 +
        normalize(get_column(df,"recent_sales_note").apply(lambda x: 1 if pd.notna(x) else 0))*0.2
    ) * 100
    # Engagement
    days_since_last_note = (datetime.today() - pd.to_datetime(get_column(df,"latest_note_date"), errors='coerce')).dt.days.fillna(0)
    df["attention_score"] = (
        normalize(get_column(df,"arr_gbp"))*0.4 +
        normalize(days_since_last_note)*0.3 +
        df["support_score"]*0.3
    ) * 100
    # Priority
    df["metric1"] = df.get("risk_score",0)
    df["metric2"] = df.get("growth_score",0)
    df["priority_score"] = df["metric1"]*0.5 + df["metric2"]*0.5 + df.get("attention_score",0)*0.2
    return df

df = compute_scores(df)
df_sorted = df.sort_values(by="priority_score", ascending=False)

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Account Prioritisation", layout="wide")
st.title("📊 Account Prioritisation Dashboard")

# Filters
segments = ["All"] + sorted(df["segment"].dropna().unique().tolist())
industries = ["All"] + sorted(df["industry"].dropna().unique().tolist())
regions = ["All"] + sorted(df["region"].dropna().unique().tolist())

seg_filter = st.selectbox("Segment", segments)
ind_filter = st.selectbox("Industry", industries)
reg_filter = st.selectbox("Region", regions)

df_filtered = df_sorted.copy()
if seg_filter != "All":
    df_filtered = df_filtered[df_filtered["segment"]==seg_filter]
if ind_filter != "All":
    df_filtered = df_filtered[df_filtered["industry"]==ind_filter]
if reg_filter != "All":
    df_filtered = df_filtered[df_filtered["region"]==reg_filter]

# -----------------------------
# Overview Section
# -----------------------------
st.subheader("📌 Overview: Top Accounts by Category")

# Accounts needing attention: top by priority
attention_accounts = df_filtered.sort_values("priority_score", ascending=False).head(5)
# Revenue at risk: top by risk_score
risk_accounts = df_filtered.sort_values("risk_score", ascending=False).head(5)
# Growth opportunities: top by growth_score
growth_accounts = df_filtered.sort_values("growth_score", ascending=False).head(5)

def render_account_block(df_block, title):
    st.markdown(f"**{title}**")
    for _, acc in df_block.iterrows():
        if st.button(f"{acc['account_name']} | Priority: {acc['priority_score']:.1f}", key=f"{title}_{acc['account_name']}"):
            st.session_state["selected_account"] = acc["account_name"]

render_account_block(attention_accounts, "Accounts Needing Attention")
render_account_block(risk_accounts, "Accounts with Revenue at Risk")
render_account_block(growth_accounts, "Accounts with Growth Opportunities")
st.markdown("---")

# -----------------------------
# Default selected account
# -----------------------------
if "selected_account" not in st.session_state:
    st.session_state["selected_account"] = df_filtered.iloc[0]["account_name"]

selected_account = st.session_state["selected_account"]
account_row = df_filtered[df_filtered["account_name"]==selected_account]

# -----------------------------
# Drill Down Section
# -----------------------------
if not account_row.empty:
    account = account_row.iloc[0]

    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Priority", f"{account.get('priority_score',0):.1f}")
    col2.metric("Risk", f"{account.get('risk_score',0):.1f}")
    col3.metric("Growth", f"{account.get('growth_score',0):.1f}")
    col4.metric("Engagement", f"{account.get('attention_score',0):.1f}")

    # Supporting Evidence Table
    st.subheader("🧠 Supporting Evidence")
    metrics_list = [
        "revenue_trend","usage_trend","open_tickets_count","sla_breaches_90d","latest_nps",
        "expansion_pipeline_gbp","seats_used","recent_sales_note","arr_gbp"
    ]
    evidence_data = {
        "Metric": [m.replace("_"," ").title() for m in metrics_list],
        "Value": [account.get(m,0) for m in metrics_list]
    }
    st.table(pd.DataFrame(evidence_data))

    # Recommended Actions
    st.subheader("✅ Recommended Actions")
    actions = []
    if account.get("risk_score",0) > 60: actions.append("🚨 Immediate customer outreach")
    if account.get("support_score",0) > 0.5: actions.append("🛠 Resolve support issues")
    if account.get("growth_score",0) > 50: actions.append("📈 Explore upsell opportunities")
    if not actions: actions.append("👀 Monitor account")
    for a in actions:
        st.write(f"- {a}")

    # Notes
    st.subheader("💾 Record Your Decision / Notes")
    notes_key = f"notes_{selected_account}"
    notes = st.text_area("Add your notes or decisions for this account", key=notes_key)
    if st.button("Save Notes"):
        file_name = "account_notes.csv"
        if os.path.exists(file_name):
            notes_df = pd.read_csv(file_name)
        else:
            notes_df = pd.DataFrame(columns=["account_name","notes"])
        if selected_account in notes_df["account_name"].values:
            notes_df.loc[notes_df["account_name"]==selected_account,"notes"] = notes
        else:
            notes_df = pd.concat([notes_df, pd.DataFrame([{"account_name": selected_account,"notes": notes}])], ignore_index=True)
        notes_df.to_csv(file_name, index=False)
        st.success("Notes saved successfully!")
else:
    st.warning(f"No data found for account '{selected_account}'")
