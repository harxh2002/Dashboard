import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- CONFIG ---
st.set_page_config(page_title="Multi-Platform ASO Keyword Rank Dashboard", layout="wide")

# --- LOGIN SYSTEM ---
client_logins = {
    "Simpl123": {
        "password": "Simpl123",
        "sheet_url": "https://docs.google.com/spreadsheets/d/1mW4oVoGARzM4nCLCd-UOWghKZ3UNZO7LxLDbMwS2NHs/edit?usp=sharing",
        "name": "Simpl"
    },
    "Nutri123": {
        "password": "Nutri123",
        "sheet_url": "https://docs.google.com/spreadsheets/d/1o3LpBXcI9teHWjTrtxUu2RlENFKp9EVMyUbnJWuGeiM/edit?usp=sharing",
        "name": "Nutristar"
    }
}

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 Client Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username in client_logins and client_logins[username]["password"] == password:
            st.session_state.authenticated = True
            st.session_state.username = username
            st.experimental_rerun()
        else:
            st.error("Invalid credentials")
    st.stop()

# --- DASHBOARD ---
client_info = client_logins[st.session_state.username]
sheet_url = client_info["sheet_url"]
st.title(f"📱 ASO Rank Dashboard - {client_info['name']}")

# --- SIDEBAR INPUTS ---
st.sidebar.header("📊 Dashboard Options")
platform = st.sidebar.radio("Select Platform", options=["Android", "iOS"])
end_date_input_str = st.sidebar.text_input("Select End Date (MM-DD-YYYY or MM/DD/YYYY)")

# --- LOAD CSV ---
def parse_flexible_date(date_str):
    for fmt in ("%m-%d-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except:
            continue
    return pd.NaT

if sheet_url and platform and end_date_input_str:
    try:
        end_date = parse_flexible_date(end_date_input_str)
        if pd.isna(end_date):
            st.error("❌ Invalid end date format. Please use MM-DD-YYYY or MM/DD/YYYY.")
            st.stop()

        sheet_id = sheet_url.split("/")[5]
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={platform}"
        df = pd.read_csv(csv_url)

        st.success(f"✅ Connected to '{platform}' tab successfully!")
        st.write("Columns:", df.columns.tolist())

        keyword_col = df.columns[0]  # first column as keyword

        raw_date_cols = df.columns[4:]
        parsed_dates = [parse_flexible_date(col) for col in raw_date_cols]
        rank_data_raw = df.iloc[:, 4:]

        rank_data = pd.DataFrame(index=df.index)
        date_lookup_map = {}  # Maps datetime.date → column name used

        for dt, cols in zip(parsed_dates, raw_date_cols):
            if pd.notna(dt):
                if dt not in date_lookup_map:
                    date_lookup_map[dt] = []
                date_lookup_map[dt].append(cols)

        processed_data = pd.DataFrame(index=df.index)
        for dt, cols in date_lookup_map.items():
            ranks = rank_data_raw[cols].apply(pd.to_numeric, errors='coerce')
            col_label = dt.strftime("%m-%d-%Y")
            processed_data[col_label] = ranks.min(axis=1)
            date_lookup_map[dt] = col_label

        end_date_col = date_lookup_map.get(end_date)

        if not end_date_col or end_date_col not in processed_data.columns:
            st.error(f"End date {end_date.strftime('%m-%d-%Y')} not found in data.")
            st.stop()

        df_filtered = df.copy()
        df_filtered["Latest Rank"] = processed_data[end_date_col]

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
        ts_data = df[df[keyword_col] == keyword_selected][processed_data.columns].T.reset_index()
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

        st.markdown("""
        <div style='text-align: right; font-size: 12px; margin-top: 50px;'>
            Built by Harsh Tiwari
        </div>
        """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"❌ Error loading Google Sheet: {e}")
