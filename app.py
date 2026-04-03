# Reasoning / Evidence as Table
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
