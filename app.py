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

        date_cols = [parse_flexible_date(col) for col in rank_data.columns]

        # --- CUSTOM DATE RANGE SELECTION ---
        st.markdown("### Select Custom Date Range")
        custom_start = st.date_input("📅 Start date", value=(datetime.today() - timedelta(days=15)).date())
        custom_end = st.date_input("📅 End date", value=datetime.today().date())

        # Convert to datetime for safe comparison
        custom_start_dt = datetime.combine(custom_start, datetime.min.time())
        custom_end_dt = datetime.combine(custom_end, datetime.min.time())

        # Filter columns within this custom range
        selected_cols = [col for col, dt in zip(rank_data.columns, date_cols)
                         if pd.notna(dt) and custom_start_dt <= dt <= custom_end_dt]

        selected_cols = sorted(selected_cols, reverse=True)  # latest to oldest
        selected_rank_data = rank_data[selected_cols]

        if len(selected_cols) < 2:
            st.warning("⚠️ Not enough date columns in selected range to process analysis.")
            st.stop()

        latest_date = selected_cols[0]
        prev_date = selected_cols[1]

        df["Latest Rank"] = selected_rank_data[latest_date]
        df["Previous Rank"] = selected_rank_data[prev_date]

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
                    return "Others"
            except:
                return "Unranked"

        df["Bucket"] = df["Latest Rank"].apply(classify_bucket)

        # --- PIE CHART ---
        bucket_counts = df["Bucket"].value_counts().reset_index()
        bucket_counts.columns = ["Bucket", "Count"]
        bucket_counts["Label"] = bucket_counts.apply(lambda x: f"{x['Bucket']} - {x['Count']} keywords", axis=1)
        pie = px.pie(bucket_counts, values="Count", names="Label", title="Rank Bucket Distribution")

        # --- LAYOUT ---
        col1, col2 = st.columns([2, 2])

        with col1:
            st.plotly_chart(pie, use_container_width=True)
            st.markdown("### Keywords by Rank Bucket")
            col3, col4, col5 = st.columns(3)
            col3.markdown("**Top 3**")
            col3.write(df[df["Bucket"] == "Top 3"][keyword_col].tolist())
            col4.markdown("**Top 5**")
            col4.write(df[df["Bucket"] == "Top 5"][keyword_col].tolist())
            col5.markdown("**Top 10**")
            col5.write(df[df["Bucket"] == "Top 10"][keyword_col].tolist())

        # --- TIME SERIES ---
        with col2:
            st.markdown("### Keyword Trend")
            keyword_selected = st.selectbox("Select a keyword", df[keyword_col].unique())

            rank_df = df[df[keyword_col] == keyword_selected][selected_cols].T.reset_index()
            rank_df.columns = ["Date", "Rank"]
            rank_df["Date"] = rank_df["Date"].apply(parse_flexible_date)
            rank_df.dropna(inplace=True)
            rank_df["Rank"] = pd.to_numeric(rank_df["Rank"], errors="coerce")

            if not rank_df.empty:
                fig = px.line(rank_df, x="Date", y="Rank", title=f"Rank trend for '{keyword_selected}'",
                              markers=True, text="Rank")
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
                if previous == "-" and latest != "-":
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
