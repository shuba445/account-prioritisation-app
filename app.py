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

df = load_data()
st.write("Columns detected in dataset:", df.columns.tolist())

# -----------------------------
# 🧮 Feature Engineering
# -----------------------------
def normalize(series):
    return (series - series.min()) / (series.max() - series.min() + 1e-9)

def compute_scores(df):
    df = df.copy()

    def safe_col(df, col):
        return df[col] if col in df.columns else pd.Series(0, index=df.index)

    # Revenue trend
    df["revenue_trend"] = (safe_col(df,"mrr_current_gbp") - safe_col(df,"mrr_3_months_ago_gbp")) / (safe_col(df,"mrr_3_months_ago_gbp")+1)
    # Usage trend
    df["usage_trend"] = (safe_col(df,"usage_current") - safe_col(df,"usage_previous")) / (safe_col(df,"usage_previous")+1)
    # Support & NPS
    df["support_score"] = normalize(safe_col(df,"open_tickets") + safe_col(df,"sla_breaches")*2)
    df["nps_score"] = 1 - normalize(safe_col(df,"nps"))
    # Risk
    df["risk_score"] = (normalize(-df["revenue_trend"])*0.25 + normalize(-df["usage_trend"])*0.25 + df["support_score"]*0.25 + df["nps_score"]*0.25)*100
    # Growth
    df["growth_score"] = (normalize(safe_col(df,"expansion_pipeline"))*0.4 + normalize(safe_col(df,"seat_utilisation"))*0.2 + normalize(df["usage_trend"])*0.2 + normalize(safe_col(df,"positive_sales_signal"))*0.2)*100
    # Attention
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
st.set_page_config(page_title="Account Prioritisation", layout="wide")
st.title("📊 Account Prioritisation Dashboard")

# Top 5 Accounts Cards
st.subheader("🏆 Top Accounts")
top_accounts = df_sorted.head(5)
cols = st.columns(5)
for i, (_, acc) in enumerate(top_accounts.iterrows()):
    with cols[i]:
        st.metric(label=acc["account_name"], value=f"{acc['priority_score']:.1f}")
        st.progress(min(acc['priority_score']/100, 1.0))

st.markdown("---")

# Portfolio Table
st.subheader("📈 Portfolio Overview")
st.dataframe(df_sorted[["account_name","priority_score","risk_score","growth_score","attention_score"]], use_container_width=True)

# -----------------------------
# Drill Down Section
# -----------------------------
st.subheader("🔍 Drill into an Account")
selected_account = st.selectbox("Select Account", df_sorted["account_name"])
account = df_sorted[df_sorted["account_name"]==selected_account].iloc[0]

# Metrics display
col1, col2, col3, col4 = st.columns(4)
col1.metric("Priority", f"{account['priority_score']:.1f}")
col2.metric("Risk", f"{account['risk_score']:.1f}")
col3.metric("Growth", f"{account['growth_score']:.1f}")
col4.metric("Attention", f"{account['attention_score']:.1f}")

# Reasoning / Evidence
st.subheader("🧠 Supporting Evidence")
with st.expander("View reasoning and supporting metrics"):
    st.write({
        "Revenue Trend": account["revenue_trend"],
        "Usage Trend": account["usage_trend"],
        "Open Tickets": account["open_tickets"],
        "SLA Breaches": account.get("sla_breaches", 0),
        "NPS": account["nps"],
        "Expansion Pipeline": account.get("expansion_pipeline", 0),
        "Seat Utilisation": account.get("seat_utilisation", 0),
        "Positive Sales Signals": account.get("positive_sales_signal", 0),
        "Days Since Last Contact": account.get("days_since_last_contact", 0),
        "ARR": account.get("arr", 0)
    })

# Recommended Actions
st.subheader("✅ Recommended Actions")
actions = []
if account["risk_score"] > 60: actions.append("🚨 Immediate customer outreach")
if account["support_score"] > 0.5: actions.append("🛠 Resolve support issues")
if account["growth_score"] > 50: actions.append("📈 Explore upsell opportunities")
if not actions: actions.append("👀 Monitor account")

for a in actions:
    st.write(f"- {a}")

# Save / Record Decisions
st.subheader("💾 Record Your Decision / Notes")
notes_key = f"notes_{selected_account}"
notes = st.text_area("Add your notes or decisions for this account", key=notes_key)
if st.button("Save Notes"):
    # Save to a local CSV file
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
