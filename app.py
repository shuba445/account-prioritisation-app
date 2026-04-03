import streamlit as st
import pandas as pd
import numpy as np
import difflib

# -----------------------------
# 📂 Load Data
# -----------------------------
@st.cache_data
def load_data():
    df = pd.read_csv("account_prioritisation_challenge_data.csv")
    return df

df = load_data()
st.write(df.columns)

# -----------------------------
# 🧮 Feature Engineering
# -----------------------------
def normalize(series):
    return (series - series.min()) / (series.max() - series.min() + 1e-9)

def compute_scores(df):
    df = df.copy()

    # Safe column getter
    def safe_col(df, col):
        if col in df.columns:
            return df[col]
        else:
            return pd.Series(0, index=df.index)

    # Revenue trend
    df["revenue_trend"] = (
        (safe_col(df, "mrr_current_gbp") - safe_col(df, "mrr_3_months_ago_gbp")) /
        (safe_col(df, "mrr_3_months_ago_gbp") + 1)
    )

    # Usage trend
    df["usage_trend"] = (
        safe_col(df, "usage_current") - safe_col(df, "usage_previous")
    ) / (safe_col(df, "usage_previous") + 1)

    # Support & NPS
    df["support_score"] = normalize(safe_col(df, "open_tickets") + safe_col(df, "sla_breaches") * 2)
    df["nps_score"] = 1 - normalize(safe_col(df, "nps"))

    # 🔴 Risk Score
    df["risk_score"] = (
        normalize(-df["revenue_trend"]) * 0.25 +
        normalize(-df["usage_trend"]) * 0.25 +
        df["support_score"] * 0.25 +
        df["nps_score"] * 0.25
    ) * 100

    # 🚀 Growth Score
    df["growth_score"] = (
        normalize(safe_col(df, "expansion_pipeline")) * 0.4 +
        normalize(safe_col(df, "seat_utilisation")) * 0.2 +
        normalize(df["usage_trend"]) * 0.2 +
        normalize(safe_col(df, "positive_sales_signal")) * 0.2
    ) * 100

    # ⚠️ Attention Score
    df["attention_score"] = (
        normalize(safe_col(df, "arr")) * 0.4 +
        normalize(safe_col(df, "days_since_last_contact")) * 0.3 +
        df["support_score"] * 0.3
    ) * 100

    return df

df = compute_scores(df)

# -----------------------------
# 🧩 Final Priority Score
# -----------------------------
# Column to sort
col_to_sort = "priority_score"

# Create dummy metrics if they don't exist
if "metric1" not in df.columns:
    df["metric1"] = df["risk_score"]
if "metric2" not in df.columns:
    df["metric2"] = df["growth_score"]
if "attention_score" not in df.columns:
    df["attention_score"] = 0  # fallback

# Calculate priority score
df["priority_score"] = (
    df["metric1"] * 0.5 +
    df["metric2"] * 0.5 +
    df["attention_score"] * 0.2
)

# Check for typos in col_to_sort
if col_to_sort not in df.columns:
    matches = difflib.get_close_matches(col_to_sort, df.columns, n=1, cutoff=0.6)
    if matches:
        st.warning(f"Column '{col_to_sort}' not found. Using '{matches[0]}' instead.")
        df = df.rename(columns={matches[0]: col_to_sort})
    else:
        raise KeyError(f"Column '{col_to_sort}' not found. Available columns: {list(df.columns)}")

# Sort by priority
df_sorted = df.sort_values(by=col_to_sort, ascending=False)

# ✅ Streamlit display (optional)
st.subheader("Top Accounts by Priority Score")
st.dataframe(
    df_sorted[["account_name", "priority_score", "risk_score", "growth_score", "attention_score"]].head(20),
    use_container_width=True
)
