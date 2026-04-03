import streamlit as st
import pandas as pd
import numpy as np
import difflib
import os

# Optional: AI Sentiment Analysis
USE_AI = False
try:
    from openai import OpenAI
    client = OpenAI()
    USE_AI = True
except:
    pass

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
        normalize(get_column(df,"seats_used")/get_column(df,"seats_purchased"))*0.2 +
        normalize(df["usage_trend"])*0.2 +
        normalize(get_column(df,"open_leads_count"))*0.2
    ) * 100

   # Engagement / Attention Score
    days_since_last_note = (pd.to_datetime("today") - pd.to_datetime(get_column(df,"latest_note_date"), errors='coerce')).dt.days.fillna(0)
    df["attention_score"] = (
    normalize(get_column(df,"arr_gbp"))*0.4 +
    normalize(days_since_last_note)*0.3 +
    df["support_score"]*0.3
    ) * 100

    # Priority Score
    df["metric1"] = df.get("risk_score",0)
    df["metric2"] = df.get("growth_score",0)
    df["priority_score"] = df["metric1"]*0.5 + df["metric2"]*0.5 + df.get("attention_score",0)*0.2

    # Normalized score for overview
    df["priority_norm"] = normalize(df["priority_score"])*100

    # AI Sentiment Score (0-1, 1 = positive)
    if USE_AI:
        sentiments = []
        for i, row in df.iterrows():
            notes = " ".join([str(row.get(c,"")) for c in ["recent_support_summary","recent_customer_note","recent_sales_note"]])
            if notes.strip()=="":
                sentiments.append(0.5)
                continue
            prompt = f"Analyze the sentiment of this customer notes and give a score between 0 (negative) to 1 (positive):\n{notes}"
            try:
                response = client.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=[{"role":"user","content":prompt}]
                )
                score_text = response.choices[0].message.content
                try:
                    score = float(score_text.strip())
                    score = min(max(score,0),1)
                except:
                    score = 0.5
                sentiments.append(score)
            except:
                sentiments.append(0.5)
        df["sentiment_score"] = sentiments
    else:
        df["sentiment_score"] = 0.5  # neutral default

    return df

df = compute_scores(df)

# -----------------------------
# Filters
# -----------------------------
st.set_page_config(page_title="Account Prioritisation", layout="wide")
st.sidebar.header("Filters")
segments = st.sidebar.multiselect("Select Segment", df["segment"].unique(), default=df["segment"].unique())
regions = st.sidebar.multiselect("Select Region", df["region"].unique(), default=df["region"].unique())
industries = st.sidebar.multiselect("Select Industry", df["industry"].unique(), default=df["industry"].unique())

df_filtered = df[df["segment"].isin(segments) & df["region"].isin(regions) & df["industry"].isin(industries)]
df_sorted = df_filtered.sort_values(by="priority_score", ascending=False)

# -----------------------------
# Top Accounts Summary
# -----------------------------
st.title("📊 Account Prioritisation Dashboard")
st.subheader("🏆 Top Accounts by Priority")
top_accounts = df_sorted.head(5)
cols = st.columns(5)
for i, (_, acc) in enumerate(top_accounts.iterrows()):
    with cols[i]:
        st.metric(acc.get("account_name","N/A"), f"{acc.get('priority_norm',0):.1f}")
        st.progress(min(acc.get("priority_norm",0)/100, 1.0))

st.markdown("---")

# -----------------------------
# Portfolio Table
# -----------------------------
st.subheader("📈 Portfolio Overview")
st.dataframe(df_sorted[[
    "account_name","segment","region","industry","priority_score","risk_score","growth_score","attention_score","priority_norm"
]], use_container_width=True)

# -----------------------------
# Quadrant Chart (native Streamlit)
# -----------------------------
st.subheader("🔲 Account Priority Quadrants")

def quadrant_category(row):
    if row["risk_score"]>50 and row["growth_score"]>50: return "Emerging"
    if row["risk_score"]>50 and row["growth_score"]<=50: return "Needs Attention"
    if row["risk_score"]<=50 and row["growth_score"]>50: return "Stable Growth"
    return "Less Focus"

quad_colors = {"Emerging":"#2ca02c","Needs Attention":"#d62728","Stable Growth":"#1f77b4","Less Focus":"#ff7f0e"}

for category in ["Emerging","Needs Attention","Stable Growth","Less Focus"]:
    st.markdown(f"### {category}")
    sub_df = df_sorted[df_sorted.apply(quadrant_category, axis=1)==category].head(3)
    if not sub_df.empty:
        for _, acc in sub_df.iterrows():
            st.write(f"**{acc['account_name']}** | Priority: {acc['priority_norm']:.1f} | Growth: {acc['growth_score']:.1f} | Risk: {acc['risk_score']:.1f} | Engagement: {acc['attention_score']:.1f}")

# -----------------------------
# Drill Down Section
# -----------------------------
st.subheader("🔍 Drill into an Account")
selected_account = st.selectbox("Select Account", df_sorted["account_name"])
account_row = df_sorted[df_sorted["account_name"]==selected_account]

if not account_row.empty:
    account = account_row.iloc[0]

    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Priority", f"{account['priority_norm']:.1f}")
    col2.metric("Risk", f"{account['risk_score']:.1f}")
    col3.metric("Growth", f"{account['growth_score']:.1f}")
    col4.metric("Engagement", f"{account['attention_score']:.1f}")

    # Executive Overview
    st.subheader("🗂 Account Overview")
    overview_cols = ["segment","region","industry","account_status","lifecycle_stage","account_owner","support_tier","contract_start_date","renewal_date","arr_gbp","seats_purchased","seats_used","latest_nps","expansion_pipeline_gbp","contraction_risk_gbp","last_qbr_date","latest_note_date","note_sentiment_hint"]
    overview_data = {col: account.get(col,"N/A") for col in overview_cols}
    st.table(pd.DataFrame(list(overview_data.items()), columns=["Attribute","Value"]))

    # Supporting Evidence Table
    st.subheader("🧠 Supporting Evidence")
    metrics_list = ["revenue_trend","usage_trend","open_tickets_count","sla_breaches_90d","latest_nps","expansion_pipeline_gbp","seats_used","open_leads_count","days_since_last_contact","arr_gbp"]
    evidence_data = {"Metric":[m.replace("_"," ").title() for m in metrics_list],"Value":[round(account.get(m,0),2) for m in metrics_list]}
    st.table(pd.DataFrame(evidence_data))

    # Recommended Actions
    st.subheader("✅ Recommended Actions")
    actions=[]
    if account["risk_score"]>60: actions.append("🚨 Immediate customer outreach")
    if account["support_score"]>0.5: actions.append("🛠 Resolve support issues")
    if account["growth_score"]>50: actions.append("📈 Explore upsell opportunities")
    if not actions: actions.append("👀 Monitor account")
    for a in actions: st.write(f"- {a}")

    # Notes
    st.subheader("💾 Record Your Decision / Notes")
    notes_key = f"notes_{selected_account}"
    notes = st.text_area("Add your notes or decisions for this account", key=notes_key)
    if st.button("Save Notes"):
        file_name="account_notes.csv"
        if os.path.exists(file_name): notes_df = pd.read_csv(file_name)
        else: notes_df = pd.DataFrame(columns=["account_name","notes"])
        if selected_account in notes_df["account_name"].values:
            notes_df.loc[notes_df["account_name"]==selected_account,"notes"] = notes
        else:
            notes_df=pd.concat([notes_df,pd.DataFrame([{"account_name":selected_account,"notes":notes}])],ignore_index=True)
        notes_df.to_csv(file_name,index=False)
        st.success("Notes saved successfully!")
else:
    st.warning(f"No data found for account '{selected_account}'.")
