import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# --- CONFIG ---
st.set_page_config(page_title="Keyword Rank Dashboard", layout="wide")
st.title("📈Keyword Ranking Dashboard")

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

        keyword_col = df.columns[0]  # auto-detect keyword column
        rank_data = df.iloc[:, 4:]

        # --- DATE PARSING ---
        def parse_flexible_date(date_str):
            for fmt in ("%m-%d-%Y", "%m/%d/%Y"):
                try:
                    return datetime.strptime(date_str, fmt)
                except:
                    continue
            return pd.NaT

        parsed_dates = [parse_flexible_date(col) for col in rank_data.columns]
        valid_date_cols = [col for col, dt in zip(rank_data.columns, parsed_dates) if pd.notna(dt)]

        # --- DATE FILTERS ---
        st.markdown("### Select Date Range")
        option = st.radio("Select range type", ["Preset Range", "Custom Range"])

        if option == "Preset Range":
            preset_range = st.selectbox("Select time range", ["Last 7 days", "Last 15 days", "Last 30 days", "Last 90 days", "Last 180 days"])
            days_map = {
                "Last 7 days": 7,
                "Last 15 days": 15,
                "Last 30 days": 30,
                "Last 90 days": 90,
                "Last 180 days": 180
            }
            days = days_map[preset_range]
            end_date = datetime.today().date()
            start_date = end_date - timedelta(days=days)
        else:
            start_date = st.date_input("Select Start Date")
            end_date = st.date_input("Select End Date")
            if start_date > end_date:
                st.error("Start date must be before end date.")
                st.stop()

        # --- COMPARISON START DATE ---
        st.markdown("### Select Comparison Start Date (For Movement Analysis)")
        comparison_date = st.date_input("Comparison Start Date")

        filtered_cols = [col for col, dt in zip(rank_data.columns, parsed_dates) if pd.notna(dt) and start_date <= dt.date() <= end_date]

        if len(filtered_cols) < 2:
            st.warning("⚠️ Not enough date columns in selected range to process analysis.")
            st.stop()

        df_filtered = df.copy()
        df_filtered["Latest Rank"] = rank_data[filtered_cols[-1]]

        # Find closest column to comparison date
        comparison_col = None
        for col, dt in zip(rank_data.columns, parsed_dates):
            if pd.notna(dt) and dt.date() == comparison_date:
                comparison_col = col
                break
        if not comparison_col:
            st.error("Comparison date not found in data.")
            st.stop()

        df_filtered["Previous Rank"] = rank_data[comparison_col]

        # --- BUCKET LOGIC ---
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
                    return None  # ✅ Exclude "Others"
            except:
                return None  # ✅ Exclude "Unranked"

        df_filtered["Bucket"] = df_filtered["Latest Rank"].apply(classify_bucket)
        df_filtered = df_filtered[df_filtered["Bucket"].notna()]  # ✅ Keep only Top 3/5/10

        # --- PIE CHART ---
        bucket_counts = df_filtered["Bucket"].value_counts().reset_index()
        bucket_counts.columns = ["Bucket", "Count"]
        bucket_counts["Label"] = bucket_counts["Bucket"] + " - " + bucket_counts["Count"].astype(str) + " keywords"
        pie = px.pie(bucket_counts, values="Count", names="Label", title="Rank Bucket Distribution")

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
                fig = px.line(ts_data, x="Date", y="Rank", markers=True, title=f"Rank trend for {keyword_selected}", text="Rank")
                fig.update_yaxes(autorange="reversed")
                fig.update_traces(textposition="top center")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No data available for this keyword in selected range.")

        # --- MOVEMENT COLUMNS ---
        st.markdown("### Keyword Movements")

        def detect_movement(latest, previous):
            try:
                latest = int(latest)
                previous = int(previous)
                if latest < previous:
                    return "Progressing"
                elif latest > previous:
                    return "Declining"
                else:
                    return "No Movement"
            except:
                if str(previous) == "-" and str(latest) != "-":
                    return "Newly Ranked"
                return "No Movement"

        df_filtered["Movement"] = df_filtered.apply(lambda row: detect_movement(row["Latest Rank"], row["Previous Rank"]), axis=1)

        st.markdown("**📈 Progressing Keywords**")
        st.dataframe(df_filtered[df_filtered["Movement"] == "Progressing"][keyword_col].dropna().reset_index(drop=True))

        st.markdown("**📉 Declining Keywords**")
        st.dataframe(df_filtered[df_filtered["Movement"] == "Declining"][keyword_col].dropna().reset_index(drop=True))

        st.markdown("**➖ No Movement**")
        st.dataframe(df_filtered[df_filtered["Movement"] == "No Movement"][keyword_col].dropna().reset_index(drop=True))

        st.markdown("**🆕 Newly Ranked**")
        st.dataframe(df_filtered[df_filtered["Movement"] == "Newly Ranked"][keyword_col].dropna().reset_index(drop=True))

    except Exception as e:
        st.error(f"❌ Error loading Google Sheet: {e}")
