import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- CONFIG ---
st.set_page_config(page_title="Keyword Rank Dashboard", layout="wide")
st.title("📈 Daily Keyword Ranking Dashboard ")

# --- SIDEBAR INPUTS ---
st.sidebar.header("🔗 Data Configuration")
sheet_url = st.sidebar.text_input("Google Sheet URL")
platform = st.sidebar.radio("Select Platform", ["Android", "iOS"])
end_date_input = st.sidebar.date_input("Select End Date")

if sheet_url:
    try:
        sheet_id = sheet_url.split("/")[5]
        platform_gid = {"Android": "0", "iOS": "1"}  # Assumes iOS is second tab, adjust as needed
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={platform_gid[platform]}"
        df = pd.read_csv(csv_url)

        st.success(f"✅ {platform} Sheet connected successfully")
        st.write("Columns:", df.columns.tolist())

        keyword_col = df.columns[0]  # first column as keyword

        def parse_flexible_date(date_str):
            for fmt in ("%m-%d-%Y", "%m/%d/%Y"):
                try:
                    return datetime.strptime(date_str, fmt).date()
                except:
                    continue
            return pd.NaT

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

        end_date = end_date_input
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

        st.divider()
        st.subheader("🎯 Rank Bucket Overview")
        bucket_counts = df_final["Bucket"].value_counts()
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Top 3", bucket_counts.get("Top 3", 0))
        col_b.metric("Top 5", bucket_counts.get("Top 5", 0))
        col_c.metric("Top 10", bucket_counts.get("Top 10", 0))

        st.divider()
        st.subheader("📊 Rank Bucket Pie Chart")
        pie_data = bucket_counts.reset_index()
        pie_data.columns = ["Bucket", "Count"]
        pie_data["Label"] = pie_data["Bucket"] + " - " + pie_data["Count"].astype(str) + " keywords"
        pie = px.pie(pie_data, values="Count", names="Label", title="Rank Bucket Distribution")
        st.plotly_chart(pie, use_container_width=True)

        st.divider()
        st.subheader("📄 Keywords by Rank Bucket")
        with st.expander("View Keyword Lists"):
            st.markdown("**Top 3**")
            st.dataframe(df_final[df_final["Bucket"] == "Top 3"][keyword_col].dropna().reset_index(drop=True))
            st.markdown("**Top 5**")
            st.dataframe(df_final[df_final["Bucket"] == "Top 5"][keyword_col].dropna().reset_index(drop=True))
            st.markdown("**Top 10**")
            st.dataframe(df_final[df_final["Bucket"] == "Top 10"][keyword_col].dropna().reset_index(drop=True))

        st.divider()
        st.subheader("📈 Keyword Trend Analysis")
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

        st.divider()
        st.subheader("📉 Daily Movement Summary")
        date_keys = list(rank_data.columns)
        date_keys_sorted = sorted(date_keys, key=lambda x: parse_flexible_date(x))

        try:
            end_idx = date_keys_sorted.index(end_date_col)
            prev_date_col = date_keys_sorted[end_idx - 1]
        except:
            st.warning("No previous date available for comparison.")
            prev_date_col = None

        if prev_date_col:
            df_filtered["Previous Rank"] = rank_data[prev_date_col]

            def detect_movement(latest, previous):
                try:
                    latest = int(latest)
                    previous = int(previous)
                    if latest < previous:
                        return "Progressed"
                    elif latest > previous:
                        return "Declined"
                    else:
                        return "No Movement"
                except:
                    if (str(previous) == "-" or pd.isna(previous)) and pd.notna(latest):
                        return "Newly Ranked"
                    return "No Movement"

            df_filtered["Movement"] = df_filtered.apply(lambda row: detect_movement(row["Latest Rank"], row["Previous Rank"]), axis=1)

            with st.expander("View Movement Details"):
                st.markdown("**📈 Progressed Keywords**")
                st.dataframe(df_filtered[df_filtered["Movement"] == "Progressed"][keyword_col].dropna().reset_index(drop=True))
                st.markdown("**📉 Declined Keywords**")
                st.dataframe(df_filtered[df_filtered["Movement"] == "Declined"][keyword_col].dropna().reset_index(drop=True))
                st.markdown("**➖ No Movement**")
                st.dataframe(df_filtered[df_filtered["Movement"] == "No Movement"][keyword_col].dropna().reset_index(drop=True))
                st.markdown("**🆕 Newly Ranked**")
                st.dataframe(df_filtered[df_filtered["Movement"] == "Newly Ranked"][keyword_col].dropna().reset_index(drop=True))

        st.markdown("""
        <div style='text-align: right; font-size: 12px; margin-top: 50px;'>
            Built by Harsh Tiwari
        </div>
        """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"❌ Error loading Google Sheet: {e}")
