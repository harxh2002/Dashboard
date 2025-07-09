import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# --- CONFIG ---
st.set_page_config(page_title="Keyword Rank Dashboard", layout="wide")
st.title("📈 Keyword Ranking Dashboard")

# --- GOOGLE SHEET INPUT ---
st.markdown("### Paste your Google Sheet link")
sheet_url = st.text_input("Google Sheet URL")

if sheet_url:
    try:
        sheet_id = sheet_url.split("/")[5]
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv"
        df = pd.read_csv(csv_url)

        st.success("✅ Google Sheet connected successfully")
        st.write("Columns:", df.columns.tolist())

        keyword_col = df.columns[0]
        rank_data = df.iloc[:, 4:]

        # --- DATE PARSING ---
        def parse_flexible_date(date_str):
            for fmt in ("%m-%d-%Y", "%m/%d/%Y", "%Y-%m-%d", "%Y/%m/%d"):
                try:
                    return datetime.strptime(date_str, fmt)
                except:
                    continue
            return pd.NaT

        parsed_dates = [parse_flexible_date(col) for col in rank_data.columns]
        valid_date_cols = [col for col, dt in zip(rank_data.columns, parsed_dates) if pd.notna(dt)]

        # --- CUSTOM DATE RANGE ONLY ---
        st.markdown("### Select Custom Date Range")
        start_date = st.date_input("Select Start Date")
        end_date = st.date_input("Select End Date")
        if start_date > end_date:
            st.error("Start date must be before end date.")
            st.stop()

        # --- FILTER COLUMNS BASED ON RANGE ---
        filtered_cols = [col for col, dt in zip(rank_data.columns, parsed_dates)
                         if pd.notna(dt) and start_date <= dt.date() <= end_date]

        if len(filtered_cols) < 1:
            st.warning("⚠️ Not enough date columns in selected range to process analysis.")
            st.stop()

        df_filtered = df.copy()
        latest_col = filtered_cols[-1]
        df_filtered["Latest Rank"] = pd.to_numeric(rank_data[latest_col], errors='coerce')

        # --- BUCKET LOGIC (CLEAN) ---
        def classify_bucket(rank):
            try:
                r = int(rank)
                if r <= 3:
                    return "Top 3"
                elif r <= 5:
                    return "Top 5"
                elif r <= 10:
                    return "Top 10"
                else:
                    return None
            except:
                return None

        df_filtered["Bucket"] = df_filtered["Latest Rank"].apply(classify_bucket)

        # --- SUMMARY COUNTS ---
        st.markdown("### 📊 Rank Bucket Summary (Based on End Date Only)")
        latest_ranks = df_filtered["Latest Rank"]
        total_keywords = latest_ranks.notna().sum()
        top3_count = latest_ranks[latest_ranks <= 3].count()
        top5_count = latest_ranks[(latest_ranks > 3) & (latest_ranks <= 5)].count()
        top10_count = latest_ranks[(latest_ranks > 5) & (latest_ranks <= 10)].count()

        colA, colB, colC, colD = st.columns(4)
        colA.metric("🔢 Total Keywords", total_keywords)
        colB.metric("🥇 Top 3", top3_count)
        colC.metric("🏅 Top 5", top5_count)
        colD.metric("🎯 Top 10", top10_count)

        # --- PIE CHART WITH PERCENTAGE ---
        bucket_counts = df_filtered["Bucket"].value_counts().reset_index()
        bucket_counts.columns = ["Bucket", "Count"]
        bucket_counts = bucket_counts[bucket_counts["Bucket"].notna()]
        bucket_counts["Percentage"] = (bucket_counts["Count"] / total_keywords) * 100
        bucket_counts["Label"] = bucket_counts["Bucket"] + " - " + \
                                 bucket_counts["Count"].astype(str) + " keywords (" + \
                                 bucket_counts["Percentage"].round(1).astype(str) + "%)"
        pie = px.pie(bucket_counts, values="Count", names="Label", title="🎯 Rank Bucket Distribution")

        # --- LAYOUT ---
        col1, col2 = st.columns([2, 2])

        with col1:
            st.plotly_chart(pie, use_container_width=True)
            st.markdown("### Keywords by Rank Bucket")
            st.markdown("**Top 3**")
            st.dataframe(df_filtered[df_filtered["Bucket"] == "Top 3"][keyword_col].dropna().reset_index(drop=True))
            st.markdown("**Top 5**")
            st.dataframe(df_filtered[df_filtered["Bucket"] == "Top 5"][keyword_col].dropna().reset_index(drop=True))
            st.markdown("**Top 10**")
            st.dataframe(df_filtered[df_filtered["Bucket"] == "Top 10"][keyword_col].dropna().reset_index(drop=True))

        # --- TIME SERIES ---
        with col2:
            st.markdown("### Keyword Trend")
            keyword_selected = st.selectbox("Select a keyword", df_filtered[keyword_col].unique())
            ts_data = df[df[keyword_col] == keyword_selected][filtered_cols].T.reset_index()
            ts_data.columns = ["Date", "Rank"]
            ts_data["Date"] = ts_data["Date"].apply(parse_flexible_date)
            ts_data.dropna(inplace=True)
            ts_data["Rank"] = pd.to_numeric(ts_data["Rank"], errors="coerce")

            if not ts_data.empty:
                fig = px.line(ts_data, x="Date", y="Rank", markers=True,
                              title=f"Rank trend for {keyword_selected}", text="Rank")
                fig.update_yaxes(autorange="reversed")
                fig.update_traces(textposition="top center")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No data available for this keyword in selected range.")

    except Exception as e:
        st.error(f"❌ Error loading Google Sheet: {e}")
