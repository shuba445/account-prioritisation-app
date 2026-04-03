import streamlit as st
import pandas as pd
import numpy as np

# Optional: AI
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

# -----------------------------
# 🧮 Feature Engineering
# -----------------------------
def normalize(series):
    return (series - series.min()) / (series.max() - series.min() + 1e-9)

def compute_scores(df):
    df = df.copy()

    # Example assumptions (adjust to actual column names)
    df["revenue_trend"] = (
    (df["mrr_current_gbp"] - df["mrr_previous_gbp"]) /
    (df["mrr_previous_gbp"] + 1)
)
    df["usage_trend"] = (df["usage_current"] - df["usage_previous"]) / (df["usage_previous"] + 1)

    df["support_score"] = normalize(df["open_tickets"] + df["sla_breaches"] * 2)
    df["nps_score"] = 1 - normalize(df["nps"])  # lower NPS = higher risk

    # 🔴 Risk
    df["risk_score"] = (
        normalize(-df["revenue_trend"]) * 0.25 +
        normalize(-df["usage_trend"]) * 0.25 +
        df["support_score"] * 0.25 +
        df["nps_score"] * 0.25
    ) * 100

    # 🚀 Growth
    df["growth_score"] = (
        normalize(df["expansion_pipeline"]) * 0.4 +
        normalize(df["seat_utilisation"]) * 0.2 +
        normalize(df["usage_trend"]) * 0.2 +
        normalize(df["positive_sales_signal"]) * 0.2
    ) * 100

    # ⚠️ Attention
    df["attention_score"] = (
        normalize(df["arr"]) * 0.4 +
        normalize(df["days_since_last_contact"]) * 0.3 +
        df["support_score"] * 0.3
    ) * 100

    # 🧩 Final Priority
    df["priority_score"] = (
        df["risk_score"] * 0.5 +
        df["growth_score"] * 0.3 +
        df["attention_score"] * 0.2
    )

    return df

df = compute_scores(df)

# -----------------------------
# 🤖 AI Explanation (Optional)
# -----------------------------
def generate_ai_summary(row):
    if not USE_AI:
        return "AI disabled"

    prompt = f"""
    Account: {row['account_name']}
    ARR: {row['arr']}
    Risk Score: {row['risk_score']:.1f}
    Growth Score: {row['growth_score']:.1f}

    Notes: {row['notes']}

    Explain:
    1. Why this account is prioritised
    2. Recommended actions
    """

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content

# -----------------------------
# 📊 Portfolio View
# -----------------------------
st.title("📊 Account Prioritisation Dashboard")

df_sorted = df.sort_values(by="priority_score", ascending=False)

st.subheader("Top Accounts to Focus On")

st.dataframe(
    df_sorted[[
        "account_name",
        "priority_score",
        "risk_score",
        "growth_score",
        "attention_score"
    ]].head(20),
    use_container_width=True
)

# -----------------------------
# 🔍 Drill Down
# -----------------------------
selected_account = st.selectbox(
    "Select Account",
    df_sorted["account_name"]
)

account = df[df["account_name"] == selected_account].iloc[0]

st.markdown("---")
st.subheader(f"📌 {selected_account}")

col1, col2, col3 = st.columns(3)

col1.metric("Risk", f"{account['risk_score']:.1f}")
col2.metric("Growth", f"{account['growth_score']:.1f}")
col3.metric("Attention", f"{account['attention_score']:.1f}")

st.metric("Priority Score", f"{account['priority_score']:.1f}")

# -----------------------------
# 🧠 Explanation
# -----------------------------
st.subheader("🧠 Why this account?")

st.write(f"""
- Revenue trend: {account['revenue_trend']:.2f}
- Usage trend: {account['usage_trend']:.2f}
- Open tickets: {account['open_tickets']}
- NPS: {account['nps']}
""")

# -----------------------------
# 🤖 AI Insights
# -----------------------------
if st.button("Generate AI Insights"):
    with st.spinner("Thinking..."):
        insight = generate_ai_summary(account)
        st.write(insight)

# -----------------------------
# ✅ Actions
# -----------------------------
st.subheader("✅ Recommended Actions")

actions = []

if account["risk_score"] > 60:
    actions.append("🚨 Immediate customer outreach")

if account["support_score"] > 0.5:
    actions.append("🛠 Resolve support issues")

if account["growth_score"] > 50:
    actions.append("📈 Explore upsell opportunity")

if not actions:
    actions.append("👀 Monitor account")

for a in actions:
    st.write(f"- {a}")
