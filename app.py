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
        normalize(get_column(df,"seats_used")/get_column(df,"seats_purchased").replace(0,1))*0.2 +
        normalize(df["usage_trend"])*0.2 +
        normalize(get_column(df,"avg_lead_score"))*0.2
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

    # Normalized scores for overview
    df["risk_norm"] = normalize(df["risk_score"])
    df["growth_norm"] = normalize(df["growth_score"])
    df["attention_norm"] = normalize(df["attention_score"])
    df["priority_norm"] = normalize(df["priority_score"])

    return df

df = compute_scores(df)

# -----------------------------
# Filters
# -----------------------------
st.sidebar.header("Filters")
segment_options = ["All"] + sorted(df["segment"].dropna().unique().tolist())
industry_options = ["All"] + sorted(df["industry"].dropna().unique().tolist())

selected_segment = st.sidebar.selectbox("Segment", segment_options)
selected_industry = st.sidebar.selectbox("Industry", industry_options)

df_filtered = df.copy()
if selected_segment != "All":
    df_filtered = df_filtered[df_filtered["segment"]==selected_segment]
if selected_industry != "All":
    df_filtered = df_filtered[df_filtered["industry"]==selected_industry]

df_sorted = df_filtered.sort_values(by="priority_score", ascending=False)

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Account Prioritisation", layout="wide")
st.title("📊 Account Prioritisation Dashboard")

# Top 3 Accounts Blocks
st.subheader("🏆 Top Accounts by Priority")
top_accounts = df_sorted.head(3)
cols = st.columns(3)
for i, (_, acc) in enumerate(top_accounts.iterrows()):
    with cols[i]:
        st.metric(label=acc.get("account_name","N/A"), value=f"{acc.get('priority_score',0):.1f}")
        st.progress(min(acc.get('priority_norm',0),1.0))

st.markdown("---")

# -----------------------------
# Quadrant Bubble Chart (Native)
# -----------------------------
st.subheader("💠 Account Quadrant Overview")
st.write("Quadrants: High Growth / Low Growth vs High Risk / Low Risk")
st.write("Bubble size indicates Priority, color indicates Engagement")

# Prepare positions
def quadrant_position(row):
    # x = Growth normalized
    # y = Risk normalized
    return row["growth_norm"], row["risk_norm"]

x_positions = df_sorted.apply(lambda r: quadrant_position(r)[0], axis=1)
y_positions = df_sorted.apply(lambda r: quadrant_position(r)[1], axis=1)
bubble_sizes = df_sorted["priority_norm"]*100  # scaled for display
bubble_colors = df_sorted["attention_norm"]

# Native plotting using Streamlit markdown + HTML for bubble representation
st.write("**Quadrant Bubble Visualization**")
max_x = 1
max_y = 1
chart_height = 400
chart_width = 600

st.write(
    f"""
    <div style="position: relative; width:{chart_width}px; height:{chart_height}px; border:1px solid #ccc;">
    """
    , unsafe_allow_html=True
)

for idx, row in df_sorted.iterrows():
    x = row["growth_norm"]
    y = row["risk_norm"]
    size = max(10, row["priority_norm"]*50)  # min size
    color_val = int(255*(1-row["attention_norm"]))
    color = f"rgb({color_val},{255-color_val},{100})"
    left = int(x*chart_width) - int(size/2)
    top = int((1-y)*chart_height) - int(size/2)
    st.write(
        f"""
        <div title="{row['account_name']} - Priority: {row['priority_score']:.1f}" 
        style="position:absolute; left:{left}px; top:{top}px; width:{size}px; height:{size}px; 
        background-color:{color}; border-radius:50%; border:1px solid #444;">
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown("---")

# -----------------------------
# Drill Down Section
# -----------------------------
st.subheader("🔍 Drill into an Account")
selected_account = st.selectbox("Select Account", df_sorted["account_name"])
account_row = df_sorted[df_sorted["account_name"]==selected_account]

if not account_row.empty:
    account = account_row.iloc[0]

    # Executive overview
    st.markdown(f"### Account Overview: {account['account_name']}")
    overview_cols = ["region","segment","industry","account_status","lifecycle_stage","account_owner",
                     "support_tier","contract_start_date","renewal_date","arr_gbp","seats_purchased",
                     "seats_used","latest_nps","expansion_pipeline_gbp","contraction_risk_gbp",
                     "last_qbr_date","latest_note_date"]
    overview_data = {col: account.get(col,"N/A") for col in overview_cols}
    st.table(pd.DataFrame(list(overview_data.items()), columns=["Field","Value"]))

    # Metrics display
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Priority", f"{round(account.get('priority_score',0))}")
    col2.metric("Risk", f"{round(account.get('risk_score',0))}")
    col3.metric("Growth", f"{round(account.get('growth_score',0))}")
    col4.metric("Engagement", f"{round(account.get('attention_score',0))}")

    # Supporting Evidence Table
    st.subheader("🧠 Supporting Evidence")
    with st.expander("View reasoning and supporting metrics"):
        metrics_list = [
            "revenue_trend","usage_trend","open_tickets_count","sla_breaches_90d","latest_nps",
            "expansion_pipeline_gbp","seats_used","avg_lead_score","days_since_last_note","arr_gbp"
        ]
        evidence_data = {
            "Metric": [m.replace("_"," ").title() for m in metrics_list],
            "Value": [round(account.get(m,0),2) for m in metrics_list]
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
            notes_df = pd.concat([notes_df, pd.DataFrame([{"account_name": selected_account,"notes": notes}])], ignore_index=True)
        notes_df.to_csv(file_name, index=False)
        st.success("Notes saved successfully!")

else:
    st.warning(f"No data found for account '{selected_account}'.")
