import streamlit as st
import pandas as pd
import numpy as np
import difflib
import os

# -----------------------------
# 🔐 Simple Authentication
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
    df = pd.read_csv("account_prioritisation_challenge_data.csv")
    return df

# -----------------------------
# Helper: get column with fallback
# -----------------------------
def get_column(df, expected_col):
    if expected_col in df.columns:
        return df[expected_col]
    else:
        # Find closest matching column
        matches = difflib.get_close_matches(expected_col, df.columns, n=1, cutoff=0.6)
        if matches:
            st.warning(f"Column '{expected_col}' not found. Using '{matches[0]}' instead.")
            return df[matches[0]]
        else:
            st.warning(f"Column '{expected_col}' not found. Using default 0.")
            return pd.Series(0, index=df.index)

# -----------------------------
# Feature Engineering
# -----------------------------
def normalize(series):
    return (series - series.min()) / (series.max() - series.min() + 1e-9)

def compute_scores(df):
    df = df.copy()

    # Revenue & usage trends
    df["revenue_trend"] = (get_column(df,"mrr_current_gbp") - get_column(df,"mrr_3_months_ago_gbp")) / (get_column(df,"mrr_3_months_ago_gbp")+1)
    df["usage_trend"] = (get_column(df,"usage_current") - get_column(df,"usage_previous")) / (get_column(df,"usage_previous")+1)

    # Support & NPS
    df["support_score"] = normalize(get_column(df,"open_tickets") + get_column(df,"sla_breaches")*2)
    df["nps_score"] = 1 - normalize(get_column(df,"nps"))

    # Risk Score
    df["risk_score"] = (
        normalize(-df["revenue_trend"])*0.25 +
        normalize(-df["usage_trend"])*0.25 +
        df["support_score"]*0.25 +
        df["nps_score"]*0.25
    ) * 100

    # Growth Score
    df["growth_score"] = (
        normalize(get_column(df,"expansion_pipeline"))*0.4 +
        normalize(get_column(df,"seat_utilisation"))*0.2 +
        normalize(df["usage_trend"])*0.2 +
        normalize(get_column(df,"positive_sales_signal"))*0.2
    ) * 100

    # Engagement / Attention Score
    df["attention_score"] = (
        normalize(get_column(df,"arr"))*0.4 +
        normalize(get_column(df,"days_since_last_contact"))*0.3 +
        df["support_score"]*0.3
    ) * 100

    # Priority Score
    df["metric1"] = df.get("risk_score",0)
    df["metric2"] = df.get("growth_score",0)
    df["priority_score"] = df["metric1"]*0.5 + df["metric2"]*0.5 + df.get("attention_score",0)*0.2

    return df

# -----------------------------
# Load & compute data
# -----------------------------
df = load_data()
df = compute_scores(df)
df_sorted = df.sort_values(by="priority_score", ascending=False)

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Account Prioritisation", layout="wide")
st.title("📊 Account Prioritisation Dashboard")

# Top 5 Accounts Cards
st.subheader("🏆 Top Accounts")
top_accounts = df_sorted.head(5)
cols = st.columns(5)
for i, (_, acc) in enumerate(top_accounts.iterrows()):
    with cols[i]:
        st.metric(label=acc.get("account_name","N/A"), value=f"{acc.get('priority_score',0):.1f}")
        st.progress(min(acc.get('priority_score',0)/100, 1.0))

st.markdown("---")

# Portfolio Table
st.subheader("📈 Portfolio Overview")
st.dataframe(df_sorted[[
    "account_name",
    "priority_score",
    "risk_score",
    "growth_score",
    "attention_score"
]], use_container_width=True)

# -----------------------------
# Drill Down Section
# -----------------------------
st.subheader("🔍 Drill into an Account")
selected_account = st.selectbox("Select Account", df_sorted["account_name"])
account_row = df_sorted[df_sorted["account_name"] == selected_account]

if not account_row.empty:
    account = account_row.iloc[0]

    # Metrics display
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Priority", f"{account.get('priority_score',0):.1f}")
    col2.metric("Risk", f"{account.get('risk_score',0):.1f}")
    col3.metric("Growth", f"{account.get('growth_score',0):.1f}")
    col4.metric("Engagement", f"{account.get('attention_score',0):.1f}")

    # Supporting Evidence Table
    st.subheader("🧠 Supporting Evidence")
    with st.expander("View reasoning and supporting metrics"):
        metrics_list = [
            "revenue_trend",
            "usage_trend",
            "open_tickets",
            "sla_breaches",
            "nps",
            "expansion_pipeline",
            "seat_utilisation",
            "positive_sales_signal",
            "days_since_last_contact",
            "arr"
        ]
        evidence_data = {
            "Metric": [m.replace("_", " ").title() for m in metrics_list],
            "Value": [account.get(m, 0) for m in metrics_list]
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

    # Save / Record Decisions
    st.subheader("💾 Record Your Decision / Notes")
    notes_key = f"notes_{selected_account}"
    notes = st.text_area("Add your notes or decisions for this account", key=notes_key)
    if st.button("Save Notes"):
        file_name = "account_notes.csv"
        if os.path.exists(file_name):
            notes_df = pd.read_csv(file_name)
        else:
            notes_df = pd.DataFrame(columns=["account_name", "notes"])
        
        if selected_account in notes_df["account_name"].values:
            notes_df.loc[notes_df["account_name"]==selected_account, "notes"] = notes
        else:
            notes_df = pd.concat([notes_df, pd.DataFrame([{"account_name": selected_account, "notes": notes}])], ignore_index=True)
        
        notes_df.to_csv(file_name, index=False)
        st.success("Notes saved successfully!")

else:
    st.warning(f"No data found for account '{selected_account}'.")
