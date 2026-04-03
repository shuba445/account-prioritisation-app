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
            st.warning(f"Column '{expected_col}' not found. Using default 0.")
            return pd.Series(0, index=df.index)

# -----------------------------
# Feature Engineering
# -----------------------------
def normalize(series):
    return (series - series.min()) / (series.max() - series.min() + 1e-9)

def compute_scores(df):
    df = df.copy()
    df["revenue_trend"] = (get_column(df,"mrr_current_gbp") - get_column(df,"mrr_3m_ago_gbp")) / (get_column(df,"mrr_3m_ago_gbp")+1)
    df["usage_trend"] = (get_column(df,"usage_score_current") - get_column(df,"usage_score_3m_ago")) / (get_column(df,"usage_score_3m_ago")+1)
    
    df["support_score"] = normalize(get_column(df,"open_tickets_count") + get_column(df,"sla_breaches_90d")*2)
    df["nps_score"] = 1 - normalize(get_column(df,"latest_nps"))
    df["positive_sales_signal"] = normalize(get_column(df,"open_leads_count") + get_column(df,"avg_lead_score"))
    df["days_since_last_contact"] = (pd.to_datetime("today") - pd.to_datetime(get_column(df,"latest_note_date"), errors='coerce')).dt.days.fillna(0)
    
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
    
    df["metric1"] = df.get("risk_score",0)
    df["metric2"] = df.get("growth_score",0)
    df["priority_score"] = df["metric1"]*0.5 + df["metric2"]*0.5 + df.get("attention_score",0)*0.2
    
    return df

df = compute_scores(df)

# -----------------------------
# Segment-normalized score
# -----------------------------
def normalize_within_segment(df, score_col="priority_score"):
    df = df.copy()
    df[f"{score_col}_norm"] = df.groupby("segment")[score_col].transform(
        lambda x: (x - x.min()) / (x.max() - x.min() + 1e-9) * 100
    )
    return df

df = normalize_within_segment(df, "priority_score")

# -----------------------------
# Streamlit UI Setup
# -----------------------------
st.set_page_config(page_title="Account Prioritisation", layout="wide")
st.title("📊 Account Prioritisation Dashboard")

# -----------------------------
# Filters
# -----------------------------
segments = df["segment"].unique()
regions = df["region"].unique()
industries = df["industry"].unique()

selected_segment = st.selectbox("Filter by Segment", ["All"]+list(segments))
selected_region = st.selectbox("Filter by Region", ["All"]+list(regions))
selected_industry = st.selectbox("Filter by Industry", ["All"]+list(industries))

df_filtered = df.copy()
if selected_segment != "All": df_filtered = df_filtered[df_filtered["segment"]==selected_segment]
if selected_region != "All": df_filtered = df_filtered[df_filtered["region"]==selected_region]
if selected_industry != "All": df_filtered = df_filtered[df_filtered["industry"]==selected_industry]

df_sorted = df_filtered.sort_values(by="priority_score", ascending=False)

# -----------------------------
# Top Accounts Cards
# -----------------------------
st.subheader("🏆 Top Accounts")
top_accounts = df_sorted.head(5)
cols = st.columns(min(5, len(top_accounts)))
for i, (_, acc) in enumerate(top_accounts.iterrows()):
    with cols[i % 5]:
        st.metric(label=acc.get("account_name","N/A"), value=f"{acc.get('priority_score',0):.1f}")
        st.progress(min(acc.get('priority_score',0)/100,1.0))

st.markdown("---")

# -----------------------------
# Portfolio Overview Table
# -----------------------------
st.subheader("📈 Portfolio Overview")
st.dataframe(df_sorted[[
    "account_name","segment","region","industry","priority_score","priority_score_norm",
    "risk_score","growth_score","attention_score"
]], use_container_width=True)

# -----------------------------
# BCG-style Quadrant Heatmap
# -----------------------------
st.subheader("📊 Account Heatmap (BCG-style)")

max_growth = df_sorted["growth_score"].max()
max_risk = df_sorted["risk_score"].max()

quadrant_labels = ["Stable Growth", "Accounts Under Threat", "Emerging", "Less Focus"]

heatmap_cols = st.columns(2)
with heatmap_cols[0]:
    for _, row in df_sorted.iterrows():
        x = row["growth_score"] / max_growth
        y = row["risk_score"] / max_risk
        size = max(5, row.get("arr_gbp", 1)/1e5)  # circle proportional to ARR
        color_score = row["priority_score_norm"]/100
        # Determine quadrant
        quadrant = ""
        if x>0.5 and y>0.5: quadrant = "Stable Growth"
        elif x<=0.5 and y>0.5: quadrant = "Accounts Under Threat"
        elif x>0.5 and y<=0.5: quadrant = "Emerging"
        else: quadrant = "Less Focus"
        st.markdown(f"- **{row['account_name']}** | Quadrant: {quadrant} | ARR: {row.get('arr_gbp',0):,.0f} | Priority (norm): {row['priority_score_norm']:.1f}")

with heatmap_cols[1]:
    st.markdown("**Quadrant Legend:**")
    st.markdown("""
    - **Stable Growth:** High growth, high risk (focus, expand)  
    - **Accounts Under Threat:** Low growth, high risk (intervene)  
    - **Emerging:** High growth, low risk (invest)  
    - **Less Focus:** Low growth, low risk (monitor)
    """)

# -----------------------------
# Drill Down Section
# -----------------------------
st.subheader("🔍 Drill into an Account")
selected_account = st.selectbox("Select Account", df_sorted["account_name"])
account_row = df_sorted[df_sorted["account_name"]==selected_account]

if not account_row.empty:
    account = account_row.iloc[0]
    
    # Executive Account Info
    st.markdown(f"""
    **Region:** {account.get('region','N/A')} | **Segment:** {account.get('segment','N/A')} | **Industry:** {account.get('industry','N/A')}  
    **Account Status:** {account.get('account_status','N/A')} | **Lifecycle Stage:** {account.get('lifecycle_stage','N/A')} | **Account Owner:** {account.get('account_owner','N/A')} | **CSM Owner:** {account.get('csm_owner','N/A')}  
    **Support Tier:** {account.get('support_tier','N/A')} | **Contract Start:** {account.get('contract_start_date','N/A')} | **Renewal Date:** {account.get('renewal_date','N/A')}  
    **ARR:** {account.get('arr_gbp',0):,.0f} | **Seats Purchased:** {account.get('seats_purchased',0)} | **Seats Used:** {account.get('seats_used',0)}  
    **Latest NPS:** {account.get('latest_nps',0)} | **Expansion Pipeline:** {account.get('expansion_pipeline_gbp',0):,.0f} | **Contraction Risk:** {account.get('contraction_risk_gbp',0):,.0f}  
    **Last QBR Date:** {account.get('last_qbr_date','N/A')} | **Latest Note Date:** {account.get('latest_note_date','N/A')} | **Note Sentiment Hint:** {account.get('note_sentiment_hint','N/A')}
    """)
    
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
            "revenue_trend","usage_trend","open_tickets_count","sla_breaches_90d","latest_nps",
            "expansion_pipeline_gbp","seats_used","positive_sales_signal","days_since_last_contact",
            "arr_gbp","recent_support_summary","recent_customer_note","recent_sales_note"
        ]
        evidence_data = {
            "Metric": [m.replace("_"," ").title() for m in metrics_list],
            "Value": [account.get(m,0) for m in metrics_list]
        }
        st.table(pd.DataFrame(evidence_data))
    
    # Recommended Actions
    st.subheader("✅ Recommended Actions")
    actions=[]
    if account.get("risk_score",0)>60: actions.append("🚨 Immediate customer outreach")
    if account.get("support_score",0)>0.5: actions.append("🛠 Resolve support issues")
    if account.get("growth_score",0)>50: actions.append("📈 Explore upsell opportunities")
    if not actions: actions.append("👀 Monitor account")
    for a in actions: st.write(f"- {a}")
    
    # Save Notes
    st.subheader("💾 Record Your Decision / Notes")
    notes_key = f"notes_{selected_account}"
    notes = st.text_area("Add notes or decisions for this account", key=notes_key)
    if st.button("Save Notes"):
        file_name = "account_notes.csv"
        if os.path.exists(file_name):
            notes_df = pd.read_csv(file_name)
        else:
            notes_df = pd.DataFrame(columns=["account_name","notes"])
        if selected_account in notes_df["account_name"].values:
            notes_df.loc[notes_df["account_name"]==selected_account,"notes"]=notes
        else:
            notes_df = pd.concat([notes_df,pd.DataFrame([{"account_name":selected_account,"notes":notes}])],ignore_index=True)
        notes_df.to_csv(file_name,index=False)
        st.success("Notes saved successfully!")

else:
    st.warning(f"No data found for account '{selected_account}'.")
