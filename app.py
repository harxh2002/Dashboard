import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- CONFIG ---
st.set_page_config(page_title="Keyword Rank Dashboard", layout="wide")
st.title("📈 Keyword Ranking Dashboard (Precise Bucket Logic)")

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

        keyword_col = df.columns[0]  # first column as keyword

        def parse_flexible_date(date_str):
            for fmt in ("%m-%d-%Y", "%m/%d/%Y"):
                try:
                    return datetime.strptime(date_str, fmt).date()
                except:
                    continue
            return pd.NaT

        # Parse date columns and group duplicates
        raw_date_cols = df.columns[4:]
        parsed_dates = [parse_flexible_date(col) for col in raw_date_cols]
        rank_data_raw = df.iloc[:, 4:]

        date_groups = {}
        for col, dt in zip(rank_data_raw.columns, parsed_dates):
            if pd.notna(dt):
                if dt not in date_groups:
                    date_groups[dt] = []
                date_groups[dt].append(col)

        rank_data = pd.DataFrame(index=df.index)
        for dt, cols in date_groups.items():
            ranks = rank_data_raw[cols].apply(pd.to_numeric, errors='coerce')
            rank_data[dt.strftime("%m-%d-%Y")] = ranks.min(axis=1)

        # --- USER INPUT ---
        st.markdown("### Select End Date")
        end_date_input = st.text_input("End Date (MM-DD-YYYY or MM/DD/YYYY)")

        if not end_date_input:
            st.stop()

        end_date = parse_flexible_date(end_date_input)
        if pd.isna(end_date):
            st.error("❌ Invalid End Date format. Use MM-DD-YYYY or MM/DD/YYYY.")
            st.stop()

        end_date_col = end_date.strftime("%m-%d-%Y")
        if end_date_col not in rank_data.columns:
            st.error(f"End date {end_date_col} not found in data.")
            st.stop()

        df_filtered = df.copy()
        df_filtered["Latest Rank"] = rank_data[end_date_col]

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
        df_final = df_filtered.dropna(subset=["Bucket"]).copy()

        # --- PIE CHART ---
        bucket_counts = df_final["Bucket"].value_counts().reset_index()
        bucket_counts.columns = ["Bucket", "Count"]
        bucket_counts["Label"] = bucket_counts["Bucket"] + " - " + bucket_counts["Count"].astype(str) + " keywords"
        pie = px.pie(bucket_counts, values="Count", names="Label", title="Rank Bucket Distribution")

        # --- LAYOUT ---
        col1, col2 = st.columns([2, 2])

        with col1:
            st.plotly_chart(pie, use_container_width=True)
            st.markdown("### Keywords by Rank Bucket")
            st.markdown("**Top 3**")
            st.dataframe(df_final[df_final["Bucket"] == "Top 3"][keyword_col].dropna().reset_index(drop=True))
            st.markdown("**Top 5**")
            st.dataframe(df_final[df_final["Bucket"] == "Top 5"][keyword_col].dropna().reset_index(drop=True))
            st.markdown("**Top 10**")
            st.dataframe(df_final[df_final["Bucket"] == "Top 10"][keyword_col].dropna().reset_index(drop=True))

        with col2:
            st.markdown("### Keyword Trend")
            keyword_selected = st.selectbox("Select a keyword", df[keyword_col].unique())
            ts_data = df[df[keyword_col] == keyword_selected][rank_data.columns].T.reset_index()
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

    except Exception as e:
        st.error(f"❌ Error loading Google Sheet: {e}")
