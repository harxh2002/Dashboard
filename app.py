import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

# --- CONFIG ---
st.set_page_config(page_title="Keyword Rank Dashboard", layout="wide")
st.title("📈 Keyword Ranking Dashboard (ML-Based)")

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
            try:
                return datetime.strptime(date_str, "%m-%d-%Y")
            except:
                try:
                    return datetime.strptime(date_str, "%m/%d/%Y")
                except:
                    raise ValueError(f"Invalid column date format: '{date_str}'. Must be MM-DD-YYYY or MM/DD/YYYY.")

        parsed_dates = [parse_flexible_date(col) for col in rank_data.columns]
        valid_date_cols = [col for col, dt in zip(rank_data.columns, parsed_dates) if pd.notna(dt)]

        # --- USER DATE INPUT ---
        st.markdown("### Select Custom Date Range")

        start_date_input = st.text_input("Start Date (MM-DD-YYYY or MM/DD/YYYY)")
        end_date_input = st.text_input("End Date (MM-DD-YYYY or MM/DD/YYYY)")

        def parse_user_date(date_str):
            for fmt in ("%m-%d-%Y", "%m/%d/%Y"):
                try:
                    return datetime.strptime(date_str, fmt).date()
                except:
                    continue
            st.error(f"❌ Invalid input: '{date_str}'. Must be MM-DD-YYYY or MM/DD/YYYY.")
            st.stop()

        if not start_date_input or not end_date_input:
            st.stop()

        start_date = parse_user_date(start_date_input)
        end_date = parse_user_date(end_date_input)

        if start_date > end_date:
            st.error("Start date must be before end date.")
            st.stop()

        filtered_cols = [col for col, dt in zip(rank_data.columns, parsed_dates) if pd.notna(dt) and start_date <= dt.date() <= end_date]

        if len(filtered_cols) < 2:
            st.warning("⚠️ Not enough date columns in selected range to process analysis.")
            st.stop()

        latest_col = filtered_cols[-1]
        df_filtered = df.copy()
        df_filtered["Latest Rank"] = rank_data[latest_col]

        # --- ML-BASED RANK BUCKET ---
        numeric_ranks = rank_data[filtered_cols].apply(pd.to_numeric, errors='coerce')
        df_ml = pd.DataFrame()
        df_ml['Keyword'] = df[keyword_col]
        df_ml['Latest'] = numeric_ranks[latest_col]
        df_ml['Avg'] = numeric_ranks.mean(axis=1)
        df_ml['Std'] = numeric_ranks.std(axis=1)
        df_ml['Days Ranked'] = numeric_ranks.notna().sum(axis=1)
        df_ml['Movement'] = numeric_ranks[filtered_cols[-1]] - numeric_ranks[filtered_cols[0]]

        def label_bucket(rank):
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

        df_ml['Target'] = df_ml['Latest'].apply(label_bucket)
        df_train = df_ml.dropna(subset=['Target'])

        features = ['Latest', 'Avg', 'Std', 'Days Ranked', 'Movement']
        X_train = df_train[features]
        y_train = LabelEncoder().fit_transform(df_train['Target'])

        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X_train, y_train)

        df_ml = df_ml.drop(columns='Target')
        df_ml['Predicted'] = model.predict(df_ml[features])
        label_map = {i: l for i, l in enumerate(['Top 3', 'Top 5', 'Top 10'])}
        df_ml['Bucket'] = df_ml['Predicted'].map(label_map)

        # --- PIE CHART ---
        bucket_counts = df_ml['Bucket'].value_counts().reset_index()
        bucket_counts.columns = ['Bucket', 'Count']
        bucket_counts['Label'] = bucket_counts['Bucket'] + ' - ' + bucket_counts['Count'].astype(str) + ' keywords'
        pie = px.pie(bucket_counts, values='Count', names='Label', title='ML-Based Rank Bucket Distribution')

        # --- LAYOUT ---
        col1, col2 = st.columns([2, 2])

        with col1:
            st.plotly_chart(pie, use_container_width=True)
            st.markdown("### Keywords by Rank Bucket")
            st.markdown("**Top 3**")
            st.dataframe(df_ml[df_ml["Bucket"] == "Top 3"]["Keyword"].dropna().reset_index(drop=True))
            st.markdown("**Top 5**")
            st.dataframe(df_ml[df_ml["Bucket"] == "Top 5"]["Keyword"].dropna().reset_index(drop=True))
            st.markdown("**Top 10**")
            st.dataframe(df_ml[df_ml["Bucket"] == "Top 10"]["Keyword"].dropna().reset_index(drop=True))

        # --- TIME SERIES ---
        with col2:
            st.markdown("### Keyword Trend")
            keyword_selected = st.selectbox("Select a keyword", df[keyword_col].unique())

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

    except Exception as e:
        st.error(f"❌ Error loading Google Sheet: {e}")
