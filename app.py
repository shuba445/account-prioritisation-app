# -----------------------------
# Drill Down Section
# -----------------------------
st.subheader("🔍 Drill into an Account")

# Select account
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

    # Reasoning / Supporting Evidence as Table
    st.subheader("🧠 Supporting Evidence")
    with st.expander("View reasoning and supporting metrics"):
        # List of metrics to display
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

        # Build table dynamically
        evidence_data = {
            "Metric": [m.replace("_", " ").title() for m in metrics_list],
            "Value": [account.get(m, 0) for m in metrics_list]
        }
        st.table(pd.DataFrame(evidence_data))

else:
    st.warning(f"No data found for account '{selected_account}'.")
