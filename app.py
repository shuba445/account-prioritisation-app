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
    df = pd.read_csv("account_prioritisation_challenge_data.csv")
    return df

df = load_data()

# -----------------------------
# Helper: map columns
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
            st.warning(f"Column '{expected_col}' not found. Using default 0.")
            return pd.Series(0, index=df.index)

# -----------------------------
# Feature Engineering
# -----------------------------
def normalize(series):
    if pd.api.types.is_numeric_dtype(series):
        return (series - series.min()) / (series.max() - series.min() + 1e-9)
    else:
        return pd.Series(0, index=series.index)

def compute_scores(df):
    df = df.copy()
    
    # Revenue & Usage Trends
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
        normalize(get_column(df,"seats_used") / (get_column(df,"seats_purchased")+1e-9))*0.2 +
        normalize(df["usage_trend"])*0.2 +
        normalize(get_column(df,"open_leads_count"))*0.2
    ) * 100
    
    # Engagement / Attention Score
    df["attention_score"] = (
        normalize(get_column(df,"arr_gbp"))*0.4 +
        normalize(pd.to_datetime("today") - pd.to_datetime(get_column(df,"latest_note_date"), errors='coerce')).dt.days.fillna(0)*0.3 +
        df["support_score"]*0.3
    )
    
    # Priority Score
    df["metric1"] = df.get("risk_score",0)
    df["metric2"] = df.get("growth_score",0)
    df["priority_score"] = df["metric1"]*0.5 + df["metric2"]*0.5 + df.get("attention_score",0)*0.2
    
    # Normalized priority for overview bubbles
    df["priority_norm"] = normalize(df["priority_score"])
    
    return df

df = compute_scores(df)
df_sorted = df.sort_values(by="priority_score", ascending=False)

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Account Prioritisation", layout="wide")
st.title("📊 Account Prioritisation Dashboard")

# -----------------------------
# Filters
# -----------------------------
industry_options = ["All"] + sorted(df["industry"].dropna().unique().tolist())
segment_options = ["All"] + sorted(df["segment"].dropna().unique().tolist())
region_options = ["All"] + sorted(df["region"].dropna().unique().tolist())

col_filter1, col_filter2, col_filter3 = st.columns(3)
selected_industry = col_filter1.selectbox("Filter by Industry", industry_options)
selected_segment = col_filter2.selectbox("Filter by Segment", segment_options)
selected_region = col_filter3.selectbox("Filter by Region", region_options)

df_filtered = df.copy()
if selected_industry != "All":
    df_filtered = df_filtered[df_filtered["industry"]==selected_industry]
if selected_segment != "All":
    df_filtered = df_filtered[df_filtered["segment"]==selected_segment]
if selected_region != "All":
    df_filtered = df_filtered[df_filtered["region"]==selected_region]

df_filtered_sorted = df_filtered.sort_values(by="priority_score", ascending=False)

# -----------------------------
# Top Accounts Summary
# -----------------------------
st.subheader("🏆 Top Accounts by Category")
attention_accounts = df_filtered_sorted.nlargest(5, "attention_score")
risk_accounts = df_filtered_sorted.nlargest(5, "risk_score")
growth_accounts = df_filtered_sorted.nlargest(5, "growth_score")

def display_account_block(df_block, title):
    st.markdown(f"**{title}**")
    for _, acc in df_block.iterrows():
        st.write(f"{acc['account_name']} | Priority: {acc['priority_score']:.1f} | Risk: {acc['risk_score']:.1f} | Growth: {acc['growth_score']:.1f} | Attention: {acc['attention_score']:.1f}")
    st.markdown("---")

display_account_block(attention_accounts, "Accounts Needing Attention")
display_account_block(risk_accounts, "Revenue at Risk")
display_account_block(growth_accounts, "Growth Opportunities")

# -----------------------------
# Account Drill-Down
# -----------------------------
st.subheader("🔍 Drill into an Account")
selected_account = st.selectbox("Select Account", df_filtered_sorted["account_name"])
account_row = df_filtered_sorted[df_filtered_sorted["account_name"]==selected_account]

if not account_row.empty:
    account = account_row.iloc[0]
    
    # Metrics display
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Priority", f"{account.get('priority_score',0):.1f}")
    col2.metric("Risk", f"{account.get('risk_score',0):.1f}")
    col3.metric("Growth", f"{account.get('growth_score',0):.1f}")
    col4.metric("Engagement", f"{account.get('attention_score',0):.1f}")
    
    # Account Overview Info
    st.subheader("🏢 Account Overview")
    info_fields = [
        "region","segment","industry","account_status","lifecycle_stage",
        "account_owner","support_tier","contract_start_date","renewal_date",
        "arr_gbp","seats_purchased","seats_used","latest_nps",
        "expansion_pipeline_gbp","contraction_risk_gbp","last_qbr_date",
        "latest_note_date","note_sentiment_hint","recent_support_summary",
        "recent_customer_note","recent_sales_note"
    ]
    overview_data = {field: account.get(field,"N/A") for field in info_fields}
    st.table(pd.DataFrame(list(overview_data.items()), columns=["Field","Value"]))
    
    # Supporting Evidence Table
    st.subheader("🧠 Supporting Evidence")
    metrics_list = [
        "revenue_trend","usage_trend","open_tickets_count","sla_breaches_90d",
        "latest_nps","expansion_pipeline_gbp","seats_used","positive_sales_signal",
        "days_since_last_contact","arr_gbp"
    ]
    evidence_data = {
        "Metric":[m.replace("_"," ").title() for m in metrics_list],
        "Value":[account.get(m,0) for m in metrics_list]
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

# -----------------------------
# Optional AI for sentiment (requires key)
# -----------------------------
USE_AI = False
try:
    from openai import OpenAI
    client = OpenAI()
    USE_AI = True
except:
    pass

if USE_AI:
    st.subheader("🤖 AI Insights")
    if st.button("Generate AI Insights for Selected Account"):
        with st.spinner("Analyzing notes..."):
            prompt = f"""
            Account: {account['account_name']}
            ARR: {account['arr_gbp']}
            Risk Score: {account['risk_score']:.1f}
            Growth Score: {account['growth_score']:.1f}
            Notes:
            Support: {account['recent_support_summary']}
            Customer: {account['recent_customer_note']}
            Sales: {account['recent_sales_note']}
            
            Explain:
            1. Why this account is prioritised
            2. Recommended actions
            """
            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[{"role":"user","content":prompt}]
            )
            st.write(response.choices[0].message.content)
