import streamlit as st
import pandas as pd
import numpy as np
import difflib
import os

# Optional AI integration
USE_AI = False
try:
    from openai import OpenAI
    client = OpenAI()
    USE_AI = True
except:
    pass

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
st.write("Columns detected:", df.columns.tolist())

# -----------------------------
# Helper: get column with fallback
# -----------------------------
def get_column(df, expected_col):
    if expected_col in df.columns:
        return df[expected_col]
    matches = difflib.get_close_matches(expected_col, df.columns, n=1, cutoff=0.6)
    if matches:
        st.warning(f"Column '{expected_col}' not found. Using '{matches[0]}' instead.")
        return df[matches[0]]
    st.warning(f"Column '{expected_col}' not found. Using 0 as default.")
    return pd.Series(0, index=df.index)

# -----------------------------
# Normalization helper
# -----------------------------
def normalize(series):
    return (series - series.min()) / (series.max() - series.min() + 1e-9)

# -----------------------------
# AI Sentiment scoring
# -----------------------------
@st.cache_data
def get_ai_sentiment(account_name, notes):
    if not USE_AI or not notes:
        return 0
    prompt = f"Analyze these notes and give a sentiment score -1 (negative), 0 (neutral), 1 (positive):\n{notes}"
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role":"user", "content":prompt}]
    )
    try:
        score = float(response.choices[0].message.content.strip())
        return max(min(score, 1), -1)
    except:
        return 0

# -----------------------------
# Compute Scores
# -----------------------------
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
        normalize(get_column(df,"seats_used")/ (get_column(df,"seats_purchased")+1))*0.2 +
        normalize(df["usage_trend"])*0.2 +
        normalize(get_column(df,"open_leads_count"))*0.2
    ) * 100

    # Attention / Engagement Score
    last_note_delta = pd.to_datetime("today") - pd.to_datetime(get_column(df,"latest_note_date"), errors='coerce')
    days_since_last_note_norm = normalize(last_note_delta.dt.days.fillna(0))
    df["attention_score"] = (
        normalize(get_column(df,"arr_gbp"))*0.4 +
        days_since_last_note_norm*0.3 +
        df["support_score"]*0.3
    ) * 100

    # Priority Score
    df["metric1"] = df.get("risk_score",0)
    df["metric2"] = df.get("growth_score",0)
    df["priority_score"] = df["metric1"]*0.5 + df["metric2"]*0.3 + df.get("attention_score",0)*0.2

    # Optional AI Sentiment Integration
    combined_notes = df["recent_support_summary"].fillna("") + " " + \
                     df["recent_customer_note"].fillna("") + " " + \
                     df["recent_sales_note"].fillna("")
    df["sentiment_score"] = [get_ai_sentiment(n, note) for n, note in zip(df["account_name"], combined_notes)]
    df["priority_score"] += df["sentiment_score"]*10  # small weight

    # Normalised priority for overview
    df["priority_norm"] = normalize(df["priority_score"])*100

    return df

df = compute_scores(df)
df_sorted = df.sort_values(by="priority_score", ascending=False)

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Account Prioritisation", layout="wide")
st.title("📊 Account Prioritisation Dashboard")

# -----------------------------
# Top Accounts Summary (clickable)
# -----------------------------
st.subheader("🏆 Top Accounts")
for category, metric, threshold in [
    ("Needs Attention", "risk_score", 60),
    ("Growth Opportunity", "growth_score", 50),
    ("Emerging Account", "attention_score", 50)
]:
    st.markdown(f"### {category}")
    top_accounts = df_sorted[df_sorted[metric] >= threshold].head(5)
    cols = st.columns(len(top_accounts))
    for i, (_, acc) in enumerate(top_accounts.iterrows()):
        with cols[i]:
            if st.button(f"{acc['account_name']} | {acc['priority_score']:.0f}", key=f"{category}_{acc['account_name']}"):
                st.session_state["selected_account"] = acc["account_name"]
            st.progress(min(acc["priority_score"]/100, 1.0))

st.markdown("---")

# Portfolio Overview
st.subheader("📈 Portfolio Overview")
st.dataframe(df_sorted[[
    "account_name","segment","region","industry","priority_score",
    "risk_score","growth_score","attention_score","sentiment_score"
]].round(1), use_container_width=True)

# -----------------------------
# Drill Down Section
# -----------------------------
st.subheader("🔍Account Details")
if "selected_account" not in st.session_state:
    st.session_state["selected_account"] = df_sorted.iloc[0]["import streamlit as st
import pandas as pd
import numpy as np
import difflib
import os

# Optional AI integration
USE_AI = False
try:
    from openai import OpenAI
    client = OpenAI()
    USE_AI = True
except:
    pass

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
st.write("Columns detected:", df.columns.tolist())

# -----------------------------
# Helper: get column with fallback
# -----------------------------
def get_column(df, expected_col):
    if expected_col in df.columns:
        return df[expected_col]
    matches = difflib.get_close_matches(expected_col, df.columns, n=1, cutoff=0.6)
    if matches:
        st.warning(f"Column '{expected_col}' not found. Using '{matches[0]}' instead.")
        return df[matches[0]]
    st.warning(f"Column '{expected_col}' not found. Using 0 as default.")
    return pd.Series(0, index=df.index)

# -----------------------------
# Normalization helper
# -----------------------------
def normalize(series):
    return (series - series.min()) / (series.max() - series.min() + 1e-9)

# -----------------------------
# AI Sentiment scoring
# -----------------------------
@st.cache_data
def get_ai_sentiment(account_name, notes):
    if not USE_AI or not notes:
        return 0
    prompt = f"Analyze these notes and give a sentiment score -1 (negative), 0 (neutral), 1 (positive):\n{notes}"
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role":"user", "content":prompt}]
    )
    try:
        score = float(response.choices[0].message.content.strip())
        return max(min(score, 1), -1)
    except:
        return 0

# -----------------------------
# Compute Scores
# -----------------------------
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
        normalize(get_column(df,"seats_used")/ (get_column(df,"seats_purchased")+1))*0.2 +
        normalize(df["usage_trend"])*0.2 +
        normalize(get_column(df,"open_leads_count"))*0.2
    ) * 100

    # Attention / Engagement Score
    last_note_delta = pd.to_datetime("today") - pd.to_datetime(get_column(df,"latest_note_date"), errors='coerce')
    days_since_last_note_norm = normalize(last_note_delta.dt.days.fillna(0))
    df["attention_score"] = (
        normalize(get_column(df,"arr_gbp"))*0.4 +
        days_since_last_note_norm*0.3 +
        df["support_score"]*0.3
    ) * 100

    # Priority Score
    df["metric1"] = df.get("risk_score",0)
    df["metric2"] = df.get("growth_score",0)
    df["priority_score"] = df["metric1"]*0.5 + df["metric2"]*0.5 + df.get("attention_score",0)*0.2

    # Optional AI Sentiment Integration
    combined_notes = df["recent_support_summary"].fillna("") + " " + \
                     df["recent_customer_note"].fillna("") + " " + \
                     df["recent_sales_note"].fillna("")
    df["sentiment_score"] = [get_ai_sentiment(n, note) for n, note in zip(df["account_name"], combined_notes)]
    df["priority_score"] += df["sentiment_score"]*10  # small weight

    # Normalised priority for overview
    df["priority_norm"] = normalize(df["priority_score"])*100

    return df

df = compute_scores(df)
df_sorted = df.sort_values(by="priority_score", ascending=False)

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Account Prioritisation", layout="wide")
st.title("📊 Account Prioritisation Dashboard")

# -----------------------------
# Top Accounts Summary (clickable)
# -----------------------------
st.subheader("🏆 Top Accounts")
for category, metric, threshold in [
    ("Needs Attention", "risk_score", 60),
    ("Growth Opportunity", "growth_score", 50),
    ("Emerging Attention", "attention_score", 50)
]:
    st.markdown(f"### {category}")
    top_accounts = df_sorted[df_sorted[metric] >= threshold].head(5)
    cols = st.columns(len(top_accounts))
    for i, (_, acc) in enumerate(top_accounts.iterrows()):
        with cols[i]:
            if st.button(f"{acc['account_name']} | {acc['priority_score']:.0f}", key=f"{category}_{acc['account_name']}"):
                st.session_state["selected_account"] = acc["account_name"]
            st.progress(min(acc["priority_score"]/100, 1.0))

st.markdown("---")

# Portfolio Overview
st.subheader("📈 Portfolio Overview")
st.dataframe(df_sorted[[
    "account_name","segment","region","industry","priority_score",
    "risk_score","growth_score","attention_score","sentiment_score"
]].round(1), use_container_width=True)

# -----------------------------
# Drill Down Section
# -----------------------------
st.subheader("🔍 Drill into an Account")
if "selected_account" not in st.session_state:
    st.session_state["selected_account"] = df_sorted.iloc[0]["account_name"]

selected_account = st.session_state["selected_account"]
account_row = df_sorted[df_sorted["account_name"] == selected_account]
if not account_row.empty:
    account = account_row.iloc[0]

    # Rounded metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Priority", f"{account['priority_score']:.0f}")
    col2.metric("Risk", f"{account['risk_score']:.0f}")
    col3.metric("Growth", f"{account['growth_score']:.0f}")
    col4.metric("Engagement", f"{account['attention_score']:.0f}")

    # Account Overview
    st.subheader("🏢 Account Overview")
    info_cols = [
        "account_name","region","segment","industry","account_status","lifecycle_stage",
        "account_owner","support_tier","contract_start_date","renewal_date",
        "arr_gbp","seats_purchased","seats_used","latest_nps",
        "expansion_pipeline_gbp","contraction_risk_gbp",
        "last_qbr_date","latest_note_date","note_sentiment_hint"
    ]
    info_data = {col: account.get(col,"") for col in info_cols}
    st.table(pd.DataFrame(list(info_data.items()), columns=["Field","Value"]))

    # Supporting Evidence
    st.subheader("🧠 Supporting Evidence")
    metrics_list = [
        "revenue_trend","usage_trend","open_tickets_count","sla_breaches_90d","latest_nps",
        "expansion_pipeline_gbp","seats_used","open_leads_count","attention_score","arr_gbp"
    ]
    evidence_data = {"Metric":[m.replace("_"," ").title() for m in metrics_list],
                     "Value":[round(account.get(m,0),1) for m in metrics_list]}
    st.table(pd.DataFrame(evidence_data))

    # Recommended Actions
    st.subheader("✅ Recommended Actions")
    actions = []
    if account.get("risk_score",0)>60: actions.append("🚨 Immediate customer outreach")
    if account.get("support_score",0)>0.5: actions.append("🛠 Resolve support issues")
    if account.get("growth_score",0)>50: actions.append("📈 Explore upsell opportunities")
    if account.get("sentiment_score",0)<0: actions.append("⚠️ Investigate negative sentiment")
    if not actions: actions.append("👀 Monitor account")
    for a in actions: st.write(f"- {a}")

    # Save Notes
    st.subheader("💾 Record Notes / Decisions")
    notes_key = f"notes_{selected_account}"
    notes = st.text_area("Add notes for this account", key=notes_key)
    if st.button("Save Notes"):
        file_name = "account_notes.csv"
        if os.path.exists(file_name):
            notes_df = pd.read_csv(file_name)
        else:
            notes_df = pd.DataFrame(columns=["account_name","notes"])
        if selected_account in notes_df["account_name"].values:
            notes_df.loc[notes_df["account_name"]==selected_account,"notes"]=notes
        else:
            notes_df = pd.concat([notes_df,pd.DataFrame([{"account_name":selected_account,"notes":notes}])], ignore_index=True)
        notes_df.to_csv(file_name,index=False)
        st.success("Notes saved successfully!")"]

selected_account = st.session_state["selected_account"]
account_row = df_sorted[df_sorted["account_name"] == selected_account]
if not account_row.empty:
    account = account_row.iloc[0]

    # Rounded metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Priority", f"{account['priority_score']:.0f}")
    col2.metric("Risk", f"{account['risk_score']:.0f}")
    col3.metric("Growth", f"{account['growth_score']:.0f}")
    col4.metric("Engagement", f"{account['attention_score']:.0f}")

    # Account Overview
    st.subheader("🏢 Account Overview")
    info_cols = [
        "region","segment","industry","account_status","lifecycle_stage",
        "account_owner","support_tier","contract_start_date","renewal_date",
        "arr_gbp","seats_purchased","seats_used","latest_nps",
        "expansion_pipeline_gbp","contraction_risk_gbp",
        "last_qbr_date","latest_note_date","note_sentiment_hint"
    ]
    info_data = {col: account.get(col,"") for col in info_cols}
    st.table(pd.DataFrame(list(info_data.items()), columns=["Field","Value"]))

    # Supporting Evidence
    st.subheader("🧠 Supporting Evidence")
    metrics_list = [
        "revenue_trend","usage_trend","open_tickets_count","sla_breaches_90d","latest_nps",
        "expansion_pipeline_gbp","seats_used","open_leads_count","attention_score","arr_gbp"
    ]
    evidence_data = {"Metric":[m.replace("_"," ").title() for m in metrics_list],
                     "Value":[round(account.get(m,0),1) for m in metrics_list]}
    st.table(pd.DataFrame(evidence_data))

    # Recommended Actions
    st.subheader("✅ Recommended Actions")
    actions = []
    if account.get("risk_score",0)>60: actions.append("🚨 Immediate customer outreach")
    if account.get("support_score",0)>0.5: actions.append("🛠 Resolve support issues")
    if account.get("growth_score",0)>50: actions.append("📈 Explore upsell opportunities")
    if account.get("sentiment_score",0)<0: actions.append("⚠️ Investigate negative sentiment")
    if not actions: actions.append("👀 Monitor account")
    for a in actions: st.write(f"- {a}")

    # Save Notes
    st.subheader("💾 Record Notes / Decisions")
    notes_key = f"notes_{selected_account}"
    notes = st.text_area("Add notes for this account", key=notes_key)
    if st.button("Save Notes"):
        file_name = "account_notes.csv"
        if os.path.exists(file_name):
            notes_df = pd.read_csv(file_name)
        else:
            notes_df = pd.DataFrame(columns=["account_name","notes"])
        if selected_account in notes_df["account_name"].values:
            notes_df.loc[notes_df["account_name"]==selected_account,"notes"]=notes
        else:
            notes_df = pd.concat([notes_df,pd.DataFrame([{"account_name":selected_account,"notes":notes}])], ignore_index=True)
        notes_df.to_csv(file_name,index=False)
        st.success("Notes saved successfully!")
