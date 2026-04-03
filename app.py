import streamlit as st
import pandas as pd
import numpy as np
import difflib
import os
import plotly.express as px

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
# Helper: get column with fallback
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
    return (series - series.min()) / (series.max() - series.min() + 1e-9)

def compute_scores(df):
    df = df.copy()

    # Revenue & usage trends
    df["revenue_trend"] = (get_column(df,"mrr_current_gbp") - get_column(df,"mrr_3m_ago_gbp")) / (get_column(df,"mrr_3m_ago_gbp")+1)
    df["usage_trend"] = (get_column(df,"usage_score_current") - get_column(df,"usage_score_3m_ago")) / (get_column(df,"usage_score_3m_ago")+1)

    # Support & NPS
    df["support_score"] = normalize(get_column(df,"open_tickets_count") + get_column(df,"sla_breaches_90d")*2)
    df["nps_score"] = 1 - normalize(get_column(df,"latest_nps"))

    # Risk Score
    df["risk_score"] = (
        normalize(-df["revenue_trend"])*0.25 +
        normalize(-df["usage_trend"])*0.25 +
        df["support_score"]*0.25 +
        df["nps_score"]*0.25
    ) * 100

    # Growth Score
    df["growth_score"] = (
        normalize(get_column(df,"expansion_pipeline_gbp"))*0.4 +
        normalize(get_column(df,"seats_used"))*0.2 +
        normalize(df["usage_trend"])*0.2 +
        normalize(get_column(df,"open_leads_count"))*0.2
    ) * 100

    # Engagement / Attention Score
    df["attention_score"] = (
        normalize(get_column(df,"arr_gbp"))*0.4 +
        normalize(get_column(df,"latest_note_date"))*0.3 +
        df["support_score"]*0.3
    ) * 100

    # Priority Score
    df["metric1"] = df.get("risk_score",0)
    df["metric2"] = df.get("growth_score",0)
    df["priority_score"] = df["metric1"]*0.5 + df["metric2"]*0.5 + df.get("attention_score",0)*0.2

    return df

df = compute_scores(df)

# -----------------------------
# Filters
# -----------------------------
st.sidebar.header("Filters")
selected_segments = st.sidebar.multiselect("Segment", df["segment"].unique(), default=df["segment"].unique())
selected_regions = st.sidebar.multiselect("Region", df["region"].unique(), default=df["region"].unique())

filtered_df = df[(df["segment"].isin(selected_segments)) & (df["region"].isin(selected_regions))]
df_sorted = filtered_df.sort_values(by="priority_score", ascending=False)

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
    "segment",
    "region",
    "priority_score",
    "risk_score",
    "growth_score",
    "attention_score"
]], use_container_width=True)

# -----------------------------
# BCG-style Heatmap
# -----------------------------
st.subheader("📊 BCG-style Account Matrix")
fig = px.scatter(
    df_sorted,
    x="growth_score",
    y="priority_score",
    size="attention_score",
    color="segment",
    hover_name="account_name",
    hover_data={
        "risk_score": True,
        "growth_score": True,
        "attention_score": True,
        "region": True
    },
    title="BCG-style Account Matrix"
)
fig.add_shape(type="line", x0=50, y0=0, x1=50, y1=100, line=dict(dash="dash", color="gray"))
fig.add_shape(type="line", x0=0, y0=50, x1=100, y1=50, line=dict(dash="dash", color="gray"))
st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# Drill Down Section
# -----------------------------
st.subheader("🔍 Drill into an Account")
selected_account = st.selectbox("Select Account", df_sorted["account_name"])
account_row = df_sorted[df_sorted["account_name"] == selected_account]

if not account_row.empty:
    account = account_row.iloc[0]

    # Executive Account Info
    st.subheader("🏢 Executive Account Overview")
    st.write({
        "Account Name": account.get("account_name", ""),
        "Segment": account.get("segment", ""),
        "Region": account.get("region", ""),
        "Account Owner": account.get("account_owner",""),
        "CSM Owner": account.get("csm_owner",""),
        "Account Status": account.get("account_status",""),
        "ARR": account.get("arr_gbp",0),
        "Seats Purchased": account.get("seats_purchased",0),
        "Seats Used": account.get("seats_used",0),
    })

    # Metrics display
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Priority", f"{account.get('priority_score',0):.1f}", help="Composite score combining risk, growth, and attention.")
    col2.metric("Risk", f"{account.get('risk_score',0):.1f}", help="Higher score indicates higher risk or potential churn.")
    col3.metric("Growth", f"{account.get('growth_score',0):.1f}", help="Higher score indicates growth opportunities.")
    col4.metric("Engagement", f"{account.get('attention_score',0):.1f}", help="Accounts needing attention based on interactions and support.")

    # Supporting Evidence Table
    st.subheader("🧠 Supporting Evidence")
    with st.expander("View reasoning and supporting metrics"):
        metrics_list = [
            "revenue_trend",
            "usage_trend",
            "open_tickets_count",
            "sla_breaches_90d",
            "latest_nps",
            "expansion_pipeline_gbp",
            "seats_used",
            "open_leads_count",
            "latest_note_date",
            "arr_gbp"
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
