import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from prophet import Prophet

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

        # --- DATE FILTER ---
        st.markdown("### Select Custom Date Range")
        start_date = st.date_input("Select Start Date")
        end_date = st.date_input("Select End Date")
        if start_date > end_date:
            st.error("Start date must be before end date.")
            st.stop()

        filtered_cols = [col for col, dt in zip(rank_data.columns, parsed_dates)
                         if pd.notna(dt) and start_date <= dt.date() <= end_date]

        if len(filtered_cols) < 2:
            st.warning("⚠️ Not enough date columns in selected range to process analysis.")
            st.stop()

        latest_col = filtered_cols[-1]
        df_filtered = df.copy()
        df_filtered["Latest Rank"] = pd.to_numeric(rank_data[latest_col], errors='coerce')

        # --- BUCKET LOGIC ---
        def classify_bucket(rank):
            try:
                r = float(rank)
                if r <= 3:
                    return "Top 3"
                elif 3 < r <= 5:
                    return "Top 5"
                elif 5 < r <= 10:
                    return "Top 10"
                else:
                    return None
            except:
                return None

        df_filtered["Bucket"] = df_filtered["Latest Rank"].apply(classify_bucket)

        # --- PIE CHART ---
        bucket_counts = df_filtered["Bucket"].value_counts().reset_index()
        bucket_counts.columns = ["Bucket", "Count"]
        bucket_counts = bucket_counts[bucket_counts["Bucket"].notna()]
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

        # --- TIME SERIES WITH FORECAST ---
        with col2:
            st.markdown("### Keyword Trend with Forecast")
            keyword_selected = st.selectbox("Select a keyword", df_filtered[keyword_col].unique())

            ts_data = df[df[keyword_col] == keyword_selected][filtered_cols].T.reset_index()
            ts_data.columns = ["Date", "Rank"]
            ts_data["Date"] = ts_data["Date"].apply(parse_flexible_date)
            ts_data.dropna(inplace=True)
            ts_data["Rank"] = pd.to_numeric(ts_data["Rank"], errors="coerce")

            if not ts_data.empty:
                prophet_df = ts_data.rename(columns={"Date": "ds", "Rank": "y"})
                model = Prophet()
                model.fit(prophet_df)
                future = model.make_future_dataframe(periods=7)
                forecast = model.predict(future)

                forecast_plot = px.line()
                forecast_plot.add_scatter(x=prophet_df["ds"], y=prophet_df["y"], mode="lines+markers", name="Actual Rank", text=prophet_df["y"])
                forecast_plot.add_scatter(x=forecast["ds"], y=forecast["yhat"], mode="lines", name="Forecast", line=dict(dash='dash'))
                forecast_plot.update_yaxes(autorange="reversed")
                forecast_plot.update_layout(title=f"Rank Trend + 7-Day Forecast for '{keyword_selected}'")
                st.plotly_chart(forecast_plot, use_container_width=True)
            else:
                st.info("No data available for this keyword in selected range.")

        # --- MOVEMENT ANALYSIS ---
        st.markdown("### Keyword Movements")

        comparison_col = filtered_cols[0]
        df_filtered["Previous Rank"] = pd.to_numeric(rank_data[comparison_col], errors="coerce")

        def detect_movement(latest, previous):
            try:
                latest = float(latest)
                previous = float(previous)
                if latest < previous:
                    return "Progressing"
                elif latest > previous:
                    return "Declining"
                else:
                    return "No Movement"
            except:
                if pd.isna(previous) and not pd.isna(latest):
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
