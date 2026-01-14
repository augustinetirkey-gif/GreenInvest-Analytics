import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import json
import sqlite3
import datetime

# Import Authenticate and Hasher from streamlit_authenticator
from streamlit_authenticator import Authenticate, Hasher

# --- Page Configuration ---
st.set_page_config(
    page_title="GreenInvest Analytics",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS FOR MAXIMUM VISIBILITY (Black Text Everywhere) ---
st.markdown("""
    <style>
        /* Force all text in the main app to be pure black */
        html, body, [data-testid="stWidgetLabel"], .stText, p, h1, h2, h3, h4, h5, h6, span, label, div {
            color: #000000 !important;
        }

        /* Set a very light background for the whole app */
        .stApp {
            background: linear-gradient(to right, #f8fff4, #f0f7e6) !important;
        }

        /* Lighten Sidebar background to make black text readable */
        section[data-testid="stSidebar"] {
            background-color: #dcedc8 !important;
            border-right: 1px solid #999;
        }

        /* Sidebar specific text and labels forcing */
        section[data-testid="stSidebar"] * {
            color: #000000 !important;
        }

        /* Tab text visibility */
        .stTabs [data-baseweb="tab"] {
            color: #000000 !important;
        }
        .stTabs [aria-selected="true"] {
            font-weight: bold;
            border-bottom: 2px solid #2e7d32 !important;
        }

        /* Metric visibility */
        [data-testid="stMetricValue"] {
            color: #000000 !important;
        }

        /* Input box adjustments for visibility */
        input {
            color: #000000 !important;
            background-color: #ffffff !important;
        }

        /* Expander and Sidebar Headers */
        .st-expanderHeader, section[data-testid="stSidebar"] h2 {
            color: #000000 !important;
        }
    </style>
""", unsafe_allow_html=True)

# Welcome banner with specific contrast for black text
st.markdown("""
    <div style="text-align:center; padding: 2rem 1rem;
            border-radius: 15px; background: #c8e6c9;
            color: #000000; border: 3px solid #1b5e20;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px;">
        <h1 style="margin:0; color: #000000;">🌿 GreenInvest Analytics</h1>
        <p style="font-size: 1.5rem; font-weight: bold; color: #1b5e20; margin:0;">Powering Sustainable Wealth 🌱</p>
    </div>
""", unsafe_allow_html=True)

# --- DATABASE FUNCTIONS ---
DATABASE_NAME = 'esg_data.db'

def init_db():
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, name TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS esg_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, timestamp TEXT NOT NULL, overall_score REAL, e_score REAL, s_score REAL, g_score REAL, env_data TEXT, social_data TEXT, gov_data TEXT, FOREIGN KEY (user_id) REFERENCES users (id))''')
    conn.commit()
    conn.close()

def add_user(username, password_hash, name):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password_hash, name) VALUES (?, ?, ?)", (username, password_hash, name))
        conn.commit()
        return True
    except sqlite3.IntegrityError: return False
    finally: conn.close()

def get_user_id(username):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username = ?", (username,))
    user_id = c.fetchone()
    conn.close()
    return user_id[0] if user_id else None

def save_esg_history(user_id, timestamp, overall, e, s, g, env_data, social_data, gov_data):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO esg_history (user_id, timestamp, overall_score, e_score, s_score, g_score, env_data, social_data, gov_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
              (user_id, timestamp, overall, e, s, g, json.dumps(env_data), json.dumps(social_data), json.dumps(gov_data)))
    conn.commit()
    conn.close()

def get_esg_history(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("SELECT timestamp, overall_score, e_score, s_score, g_score, env_data, social_data, gov_data FROM esg_history WHERE user_id = ? ORDER BY timestamp ASC", (user_id,))
    history_data = c.fetchall()
    conn.close()
    parsed_history = []
    for row in history_data:
        parsed_history.append({'timestamp': pd.to_datetime(row[0]), 'overall_score': row[1], 'e_score': row[2], 's_score': row[3], 'g_score': row[4], 'env_data': json.loads(row[5]) if row[5] else None, 'social_data': json.loads(row[6]) if row[6] else None, 'gov_data': json.loads(row[7]) if row[7] else None})
    return parsed_history

init_db()

# --- MOCK DATA & HELPERS ---
FINANCE_OPPORTUNITIES = [
    {"name": "GreenStart Grant Program", "type": "Grant", "description": "Covers 50% of energy audit costs.", "minimum_esg_score": 0, "icon": "🌱", "url": "https://www.sba.gov/funding-programs/grants"},
    {"name": "Eco-Efficiency Loan", "type": "Loan", "description": "Low-interest loans for energy equipment.", "minimum_esg_score": 60, "icon": "💡", "url": "https://www.bankofamerica.com/smallbusiness/business-financing/"},
    {"name": "Sustainable Supply Chain Fund", "type": "Venture Capital", "description": "Equity investment for companies.", "minimum_esg_score": 75, "icon": "🤝", "url": "https://www.blackrock.com/corporate/sustainability"},
    {"name": "Impact Investors Alliance", "type": "Private Equity", "description": "Access to global sustainable networks.", "minimum_esg_score": 90, "icon": "🏆", "url": "https://thegiin.org/"}
]

INDUSTRY_AVERAGES = {'Environmental': 70, 'Social': 65, 'Governance': 75, 'Overall ESG': 70}
CO2_EMISSION_FACTORS = {'energy_kwh_to_co2': 0.4, 'water_m3_to_co2': 0.1, 'waste_kg_to_co2': 0.5}

def calculate_esg_score(env_data, social_data, gov_data):
    weights = {'E': 0.4, 'S': 0.3, 'G': 0.3}
    e_score = (max(0, 100 - (env_data['energy'] / 1000)) + max(0, 100 - (env_data['water'] / 500)) + max(0, 100 - (env_data['waste'] / 100)) + env_data['recycling']) / 4
    s_score = (max(0, 100 - (social_data['turnover'] * 2)) + max(0, 100 - (social_data['incidents'] * 10)) + social_data['diversity']) / 3
    g_score = (gov_data['independence'] + gov_data['ethics']) / 2
    final_score = (e_score * weights['E']) + (s_score * weights['S']) + (g_score * weights['G'])
    return final_score, e_score, s_score, g_score

def get_recommendations(e_score, s_score, g_score):
    recs = {'E': [], 'S': [], 'G': []}
    if e_score < 70: recs['E'].append("**High Impact:** Conduct a professional energy audit.")
    if s_score < 70: recs['S'].append("**High Impact:** Introduce an anonymous employee feedback system.")
    if g_score < 75: recs['G'].append("**High Impact:** Appoint an additional independent director.")
    for k in recs:
        if not recs[k]: recs[k].append("Strong performance! Continue monitoring metrics.")
    return recs

def calculate_environmental_impact(env_data):
    energy_co2 = env_data.get('energy', 0) * CO2_EMISSION_FACTORS['energy_kwh_to_co2']
    water_co2 = env_data.get('water', 0) * CO2_EMISSION_FACTORS['water_m3_to_co2']
    waste_co2 = env_data.get('waste', 0) * CO2_EMISSION_FACTORS['waste_kg_to_co2']
    return {'total_co2_kg': energy_co2 + water_co2 + waste_co2, 'energy_co2_kg': energy_co2, 'water_co2_kg': water_co2, 'waste_co2_kg': waste_co2}

# --- Dashboard Component ---
def display_dashboard(final_score, e_score, s_score, g_score, env_data, social_data, gov_data, current_user_id):
    st.header(f"Your ESG Performance Dashboard, {st.session_state.name}!")
    st.metric(label="Overall ESG Score", value=f"{final_score:.1f}", delta="out of 100")
    st.divider()

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Overview", "🎯 Actions", "💰 Finance", "🕰️ History", "🧪 Scenario"])

    with tab1:
        st.subheader("Performance Breakdown")
        col_e, col_s, col_g = st.columns(3)
        col_e.metric("🌳 Environmental", f"{e_score:.1f}")
        col_s.metric("❤️ Social", f"{s_score:.1f}")
        col_g.metric("⚖️ Governance", f"{g_score:.1f}")
        
        impact = calculate_environmental_impact(env_data)
        st.info(f"Estimated Annual CO2: **{impact['total_co2_kg']:.2f} kg**")
        
        fig_spider = go.Figure()
        fig_spider.add_trace(go.Scatterpolar(r=[e_score, s_score, g_score, e_score], theta=['Env', 'Social', 'Gov', 'Env'], fill='toself', name='You'))
        fig_spider.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), font=dict(color="black"))
        st.plotly_chart(fig_spider, use_container_width=True)

    with tab2:
        st.header("Recommendations")
        recs = get_recommendations(e_score, s_score, g_score)
        for cat, list_recs in recs.items():
            st.subheader(cat)
            for r in list_recs: st.write(f"- {r}")

    with tab3:
        st.header("Finance Marketplace")
        unlocked = [opp for opp in FINANCE_OPPORTUNITIES if final_score >= opp['minimum_esg_score']]
        for opp in unlocked:
            with st.container(border=True):
                st.subheader(f"{opp['icon']} {opp['name']}")
                st.write(opp['description'])
                st.link_button("Apply", opp['url'])

    with tab4:
        st.header("Historical Trends")
        history = get_esg_history(current_user_id)
        if history:
            h_df = pd.DataFrame(history)
            fig_hist = go.Figure(go.Scatter(x=h_df['timestamp'], y=h_df['overall_score'], mode='lines+markers'))
            fig_hist.update_layout(title="ESG Progress", font=dict(color="black"))
            st.plotly_chart(fig_hist, use_container_width=True)
        else: st.info("No history yet.")

# --- Authentication Logic ---
def get_auth_credentials():
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("SELECT name, username, password_hash FROM users")
    users_data = c.fetchall()
    conn.close()
    credentials = {"usernames": {}}
    for name, user, pw in users_data:
        credentials["usernames"][user] = {"name": name, "password": pw}
    return credentials

creds = get_auth_credentials()
authenticator = Authenticate(creds, 'green_cookie', 'secret_key', 30)
name, auth_status, username = authenticator.login(form_name='Login', location='main')

if st.session_state["authentication_status"]:
    st.session_state.username = username
    st.session_state.name = name
    st.session_state.user_id = get_user_id(username)
    authenticator.logout('Logout', location='sidebar')
    
    st.sidebar.header("Step 1: Input Data")
    input_method = st.sidebar.radio("Method", ("Manual Input", "Upload CSV"))

    if input_method == "Manual Input":
        with st.sidebar.expander("🌳 Environmental", expanded=True):
            e_kwh = st.number_input("Energy (kWh)", 0, value=50000)
            w_m3 = st.number_input("Water (m3)", 0, value=2500)
            w_kg = st.number_input("Waste (kg)", 0, value=1000)
            rec_pct = st.slider("Recycling (%)", 0, 100, 40)
        
        if st.sidebar.button("Calculate ESG Score", type="primary"):
            env = {'energy': e_kwh, 'water': w_m3, 'waste': w_kg, 'recycling': rec_pct}
            soc = {'turnover': 15, 'incidents': 3, 'diversity': 30}
            gov = {'independence': 50, 'ethics': 85}
            fs, es, ss, gs = calculate_esg_score(env, soc, gov)
            save_esg_history(st.session_state.user_id, datetime.datetime.now().isoformat(), fs, es, ss, gs, env, soc, gov)
            display_dashboard(fs, es, ss, gs, env, soc, gov, st.session_state.user_id)
    else:
        uploaded_file = st.sidebar.file_uploader("Upload CSV", type=["csv"])
        if uploaded_file:
            st.success("File uploaded! Logic processing...")

elif st.session_state["authentication_status"] is False:
    st.error('Username/password is incorrect.')
elif st.session_state["authentication_status"] is None:
    st.info('Please log in or register below.')
    with st.expander("New User? Register Here", expanded=True):
        new_name = st.text_input("Name", key="reg_n")
        new_user = st.text_input("Username", key="reg_u")
        new_pass = st.text_input("Password", type="password", key="reg_p")
        if st.button("Register"):
            hashed = Hasher([new_pass]).generate()[0]
            if add_user(new_user, hashed, new_name):
                st.success("Registered! Please login above.")
            else: st.error("Username exists.")

st.divider()
st.write("Made with ❤️ for a greener future. – GreenInvest Analytics")
