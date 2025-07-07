import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# --- CONFIG ---
st.set_page_config(page_title="Keyword Rank Dashboard", layout="wide")
st.title("📈 CribApp Keyword Ranking Dashboard")

# --- GOOGLE SHEET INPUT ---
st.markdown("### Paste your Google Sheet link")
sheet_url = st.text_input("Google Sheet URL")

if sheet_url:
    try:
        sheet_id = sheet_url.split("/")[5]
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv"
        df = pd.read_csv(csv_url)

        st.success("✅ Google Sheet connected successfully")

        keyword_col = df.columns[0]  # Keyword column
        rank_data = df.iloc[:, 4:]

        def parse_flexible_date(date_str):
            for fmt in ("%m-%d-%Y", "%m/%d/%Y"):
                try:
                    return datetime.strptime(date_str, fmt)
                except:
                    continue
            return pd.NaT

        parsed_dates = [(col, parse_flexible_date(col)) for col in rank_data.columns if parse_flexible_date(col)]
        all_dates = [dt for _, dt in parsed_dates if pd.notna(dt)]

        st.markdown("### Select Date Range")
        col1, col2 = st.columns(2)

        predefined_range = col1.selectbox("Quick Range", ["Last 7 days", "Last 15 days", "Last 30 days", "Last 90 days", "Last 180 days", "Custom Range"])

        if predefined_range != "Custom Range":
            days_map = {"Last 7 days": 7, "Last 15 days": 15, "Last 30 days": 30, "Last 90 days": 90, "Last 180 days": 180}
            end_date = datetime.today()
            start_date = end_date - timedelta(days=days_map[predefined_range])
        else:
            start_date = col1.date_input("Start Date", value=datetime.today() - timedelta(days=7))
            end_date = col2.date_input("End Date", value=datetime.today())

        # Select comparison start date separately
        st.markdown("### Select Comparison Start Date (For Movement Analysis)")
        all_date_options = sorted([dt for _, dt in parsed_dates if pd.notna(dt)])
        filtered_date_options = [dt for dt in all_date_options if start_date <= dt <= end_date]
        selected_base_date = st.selectbox("Select base date", [dt.strftime("%m-%d-%Y") for dt in filtered_date_options])
        base_col = next((col for col, dt in parsed_dates if dt.strftime("%m-%d-%Y") == selected_base_date), None)

        # Filter columns strictly within selected date range
        filtered_cols = [col for col, dt in parsed_dates if start_date <= dt <= end_date]
        if len(filtered_cols) < 2:
            st.warning("Not enough data in selected range.")
            st.stop()

        latest_col = filtered_cols[0]  # Always use latest column from range

        df["Latest Rank"] = df[latest_col]
        df["Previous Rank"] = df[base_col]

        # --- RANK BUCKET ---
        def classify_bucket(rank):
            try:
                r = int(rank)
                if r <= 3: return "Top 3"
                elif r <= 5: return "Top 5"
                elif r <= 10: return "Top 10"
                else: return "Others"
            except:
                return "Unranked"

        df["Bucket"] = df["Latest Rank"].apply(classify_bucket)
        bucket_counts = df["Bucket"].value_counts().reset_index()
        bucket_counts.columns = ["Bucket", "Count"]
        bucket_counts["Label"] = bucket_counts["Bucket"] + " - " + bucket_counts["Count"].astype(str) + " keywords"
        pie = px.pie(bucket_counts, values="Count", names="Label", title="Rank Bucket Distribution")

        # --- VISUALS ---
        col3, col4 = st.columns([2, 2])
        with col3:
            st.plotly_chart(pie, use_container_width=True)
            st.markdown("### Keywords by Rank Bucket")
            col_a, col_b, col_c = st.columns(3)
            col_a.write(df[df["Bucket"] == "Top 3"][keyword_col].tolist())
            col_b.write(df[df["Bucket"] == "Top 5"][keyword_col].tolist())
            col_c.write(df[df["Bucket"] == "Top 10"][keyword_col].tolist())

        with col4:
            st.markdown("### Keyword Time Series Trend")
            selected_keyword = st.selectbox("Select a keyword", df[keyword_col].unique())
            trend_df = df[df[keyword_col] == selected_keyword][filtered_cols].T.reset_index()
            trend_df.columns = ["Date", "Rank"]
            trend_df["Date"] = trend_df["Date"].apply(parse_flexible_date)
            trend_df["Rank"] = pd.to_numeric(trend_df["Rank"], errors="coerce")
            trend_df.dropna(inplace=True)

            if not trend_df.empty:
                fig = px.line(trend_df, x="Date", y="Rank", text="Rank", title=f"Rank Trend: {selected_keyword}", markers=True)
                fig.update_traces(textposition="top center")
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No data available for this keyword in selected range.")

        # --- MOVEMENT COLUMNS ---
        st.markdown("### Keyword Movements")
        col6, col7, col8, col9 = st.columns(4)

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

        df["Movement"] = df.apply(lambda row: detect_movement(row["Latest Rank"], row["Previous Rank"]), axis=1)

        col6.markdown("**📈 Progressing**")
        col6.write(df[df["Movement"] == "Progressing"][keyword_col].tolist())

        col7.markdown("**📉 Declining**")
        col7.write(df[df["Movement"] == "Declining"][keyword_col].tolist())

        col8.markdown("**➖ No Movement**")
        col8.write(df[df["Movement"] == "No Movement"][keyword_col].tolist())

        col9.markdown("**🆕 Newly Ranked**")
        col9.write(df[df["Movement"] == "Newly Ranked"][keyword_col].tolist())

    except Exception as e:
        st.error(f"❌ Error loading Google Sheet: {e}")
