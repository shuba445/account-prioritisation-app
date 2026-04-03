# -----------------------------
# Drill Down Section
# -----------------------------
st.subheader("🔍 Drill into an Account")
selected_account = st.selectbox("Select Account", df_sorted["account_name"])
account = df_sorted[df_sorted["account_name"] == selected_account].iloc[0]

# Metrics display
col1, col2, col3, col4 = st.columns(4)
col1.metric("Priority", f"{account.get('priority_score',0):.1f}")
col2.metric("Risk", f"{account.get('risk_score',0):.1f}")
col3.metric("Growth", f"{account.get('growth_score',0):.1f}")
col4.metric("Engagement", f"{account.get('attention_score',0):.1f}")

# Reasoning / Supporting Evidence as Table
st.subheader("🧠 Supporting Evidence")
with st.expander("View reasoning and supporting metrics"):
    evidence_data = {
        "Metric": [
            "Revenue Trend",
            "Usage Trend",
            "Open Tickets",
            "SLA Breaches",
            "NPS",
            "Expansion Pipeline",
            "Seat Utilisation",
            "Positive Sales Signals",
            "Days Since Last Contact",
            "ARR"
        ],
        "Value": [
            account.get("revenue_trend",0),
            account.get("usage_trend",0),
            account.get("open_tickets",0),
            account.get("sla_breaches",0),
            account.get("nps",0),
            account.get("expansion_pipeline",0),
            account.get("seat_utilisation",0),
            account.get("positive_sales_signal",0),
            account.get("days_since_last_contact",0),
            account.get("arr",0)
        ]
    }
    st.table(pd.DataFrame(evidence_data))
