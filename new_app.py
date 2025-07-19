import os
import json
import pandas as pd
import yfinance as yf
from datetime import datetime
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st

# Write creds.json dynamically from env variable (Render/Railway-safe)
if not os.path.exists("creds.json") and "GCP_CREDENTIALS" in os.environ:
    with open("creds.json", "w") as f:
        json.dump(json.loads(os.environ["GCP_CREDENTIALS"]), f)

# Set page config and styles
st.set_page_config(
    page_title="Stock Portfolio Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    :root {
        --primary: #4f8bf9;
        --secondary: #6c757d;
        --success: #28a745;
        --danger: #dc3545;
        --warning: #ffc107;
        --info: #17a2b8;
        --light: #f8f9fa;
        --dark: #343a40;
    }
    
    .stApp {
        background-color: #f5f7fa;
    }
    
    [data-testid="stSidebar"] {
        background-color: #2c3e50 !important;
        color: white !important;
    }
    
    h1, h2, h3, h4, h5, h6 {
        color: var(--dark) !important;
    }
    
    .stButton>button {
        border-radius: 8px !important;
        padding: 8px 16px !important;
        font-weight: 500 !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1) !important;
    }
    
    .stDataFrame {
        border-radius: 8px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
    }
    
    .card {
        background: white;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    
    .metric-card {
        background: white;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border-left: 4px solid var(--primary);
    }
    
    .stock-card {
        background: white;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        transition: all 0.3s ease;
    }
    
    .positive {
        color: var(--success) !important;
    }
    
    .negative {
        color: var(--danger) !important;
    }
</style>
""", unsafe_allow_html=True)

# Google Sheets functions
def connect_to_gsheet():
    if "creds" not in st.session_state or "sheet_name" not in st.session_state or "worksheet" not in st.session_state:
        return None
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(st.session_state["creds"], scope)
        client = gspread.authorize(creds)
        sheet = client.open(st.session_state["sheet_name"]).worksheet(st.session_state["worksheet"])
        return sheet
    except Exception as e:
        st.error(f"Error connecting to Google Sheet: {e}")
        return None

def load_data():
    try:
        sheet = connect_to_gsheet()
        df = get_as_dataframe(sheet)
        df = df.dropna(how="all")
        return df
    except Exception as e:
        st.error(f"Error loading from Google Sheet: {e}")
        return pd.DataFrame()

def save_data(df):
    try:
        sheet = connect_to_gsheet()
        sheet.clear()
        set_with_dataframe(sheet, df)
    except Exception as e:
        st.error(f"Error saving to Google Sheet: {e}")

# Stock data functions
def get_current_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")
        if not hist.empty:
            return round(hist["Close"].iloc[-1], 2)
        return None
    except Exception as e:
        st.error(f"Error fetching stock price: {e}")
        return None

def get_current_spy():
    try:
        spy = yf.Ticker("SPY")
        hist = spy.history(period="1d")
        if not hist.empty:
            return round(hist["Close"].iloc[-1], 2)
        return None
    except Exception:
        return None

# UI Components
def show_add_entry():
    st.header("➕ Add New Portfolio Entry")
    
    with st.container():
        st.markdown("""
        <div class="card">
            <p style="margin-bottom: 0; color: var(--secondary);">
                Add a new stock to your portfolio. All fields are required.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    existing_df = load_data()
    if not existing_df.empty:
        existing_df["B_Date"] = pd.to_datetime(existing_df["B_Date"], errors='coerce')
        existing_df["Days"] = existing_df["B_Date"].apply(lambda d: (datetime.today().date() - d.date()).days if pd.notnull(d) and hasattr(d, 'date') else '')
        
        tab1, tab2 = st.tabs(["📊 Portfolio Summary", "📈 Performance Metrics"])
        
        with tab1:
            st.dataframe(
                existing_df.style.format({
                    "$ up/down": "${:,.2f}",
                    "% up/down": "{:.2f}%",
                    "Buy value": "${:,.2f}",
                    "Current value": "${:,.2f}",
                    "Stop Loss Profit": "${:,.2f}",
                    "Stop_loss_%": "{:.2f}%"
                }).applymap(lambda x: "color: #28a745" if isinstance(x, (int, float)) and x > 0 else "color: #dc3545" if isinstance(x, (int, float)) and x < 0 else ""),
                use_container_width=True,
                height=400
            )
        
        with tab2:
            if not existing_df.empty:
                total_investment = existing_df["Buy value"].sum()
                current_value = existing_df["Current value"].sum()
                total_profit = current_value - total_investment
                profit_percent = (total_profit / total_investment) * 100 if total_investment else 0
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Investment", f"${total_investment:,.2f}")
                with col2:
                    st.metric("Current Value", f"${current_value:,.2f}")
                with col3:
                    st.metric("Total Profit/Loss", 
                             f"${total_profit:,.2f}",
                             f"{profit_percent:.2f}%",
                             delta_color="inverse" if total_profit < 0 else "normal")

    # Price fetching section (outside the form)
    price_col1, price_col2 = st.columns([3, 1])
    with price_col1:
        ticker = st.text_input("Stock Ticker (e.g., AAPL)", placeholder="AAPL", key="ticker_input")
    with price_col2:
        if st.button("Get Current Price", key="get_price_button"):
            if ticker:
                current_price = get_current_price(ticker)
                if current_price:
                    st.session_state.current_price = current_price
                    st.success(f"Current {ticker.upper()} price: ${current_price:.2f}")
                else:
                    st.error(f"Could not fetch price for {ticker.upper()}")
            else:
                st.warning("Please enter a stock ticker first")

    # Show current price if available
    if "current_price" in st.session_state:
        st.info(f"Current price for {ticker.upper() if ticker else 'selected stock'}: ${st.session_state.current_price:.2f}")

    # Main form for submitting the entry
    with st.form("stock_entry_form"):
        st.markdown("### Stock Information")
        col1, col2 = st.columns(2)
        with col1:
            buy_price = st.number_input("Buy Price ($)", min_value=0.0, format="%.2f", step=0.01, key="buy_price")
            pur_spy = st.number_input("SPY Purchase Price ($)", min_value=0.0, format="%.2f", step=0.01, key="pur_spy")
        with col2:
            shares = st.number_input("Number of Shares", min_value=1, step=1, key="shares")
            stop_loss = st.number_input("Stop Loss Price ($)", min_value=0.0, format="%.2f", step=0.01, key="stop_loss")
            remark = st.text_input("Remark/Notes", placeholder="e.g., Tech sector, long-term hold", key="remark")

        if pur_spy:
            current_spy = get_current_spy()
            if current_spy:
                st.info(f"Current SPY price: ${current_spy:.2f}")

        submitted = st.form_submit_button("➕ Add to Portfolio", type="primary")
        
        if submitted:
            if not ticker:
                st.error("Please enter a stock ticker")
                return
            
            current_price = get_current_price(ticker) if "current_price" not in st.session_state else st.session_state.current_price
            
            if not current_price:
                st.error("Could not fetch current price. Please check the ticker and try again.")
                return
            
            try:
                df = load_data()
                df = df[df['Ticker'] != 'Total'] if not df.empty else df

                today = datetime.today().date()
                buy_value = shares * buy_price
                current_value = shares * current_price
                stop_loss_profit = (stop_loss - buy_price) * shares
                dollar_up_down = current_value - buy_value
                percent_up_down = ((current_price / buy_price) - 1) * 100
                stop_loss_percent = (stop_loss_profit / buy_value) * 100
                current_spy = get_current_spy()
                days_held = (today - today).days
                spy_perc = round(((current_spy - pur_spy) / pur_spy) * 100, 2) if pur_spy else 0

                new_row = {
                    "Ticker": ticker.upper(),
                    "# of shares": shares,
                    "Buy stock price": buy_price,
                    "Current stock price": current_price,
                    "Stop Loss": stop_loss,
                    "Stop Loss Profit": round(stop_loss_profit, 2),
                    "$ up/down": round(dollar_up_down, 2),
                    "% up/down": round(percent_up_down, 2),
                    "Stop_loss_%": round(stop_loss_percent, 2),
                    "Buy value": round(buy_value, 2),
                    "Current value": round(current_value, 2),
                    "B_Date": today,
                    "Days": 0,
                    "Current_Spy": current_spy,
                    "SPY_Per%": spy_perc,
                    "Holding": 1,
                    "Profit%_Portfolio": 0.0,
                    "Stoploss_Portfolio%": 0.0,
                    "Remark": remark
                }

                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                df["B_Date"] = pd.to_datetime(df["B_Date"], errors='coerce')
                df["Days"] = df["B_Date"].apply(lambda d: (datetime.today().date() - d.date()).days if pd.notnull(d) and hasattr(d, 'date') else '')
                df = df[df["Ticker"] != "Total"]

                for col in ["Profit%_Portfolio", "Stoploss_Portfolio%"]:
                    if col not in df.columns:
                        df[col] = 0.0

                total_up_down = df["$ up/down"].astype(float).sum()
                total_sl_profit = df["Stop Loss Profit"].astype(float).sum()

                df["Profit%_Portfolio"] = df["$ up/down"].apply(
                    lambda x: round((float(x) / total_up_down) * 100, 2) if total_up_down else 0
                )
                df["Stoploss_Portfolio%"] = df["Stop Loss Profit"].apply(
                    lambda x: round((float(x) / total_sl_profit) * 100, 2) if total_sl_profit else 0
                )

                exclude_from_total = ["Ticker", "B_Date", "Holding", "Profit%_Portfolio", "Stoploss_Portfolio%"]
                total_row = {}
                for col in df.columns:
                    if col in exclude_from_total:
                        total_row[col] = "Total" if col == "Ticker" else ""
                    elif pd.api.types.is_numeric_dtype(df[col]):
                        total_row[col] = df[col].sum()
                    else:
                        total_row[col] = ""

                total_row["Profit%_Portfolio"] = 100.0
                total_row["Stoploss_Portfolio%"] = 100.0
                df = pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)
                save_data(df)
                st.success("✅ Entry added and totals updated successfully!")
                st.balloons()
                # Clear the current price from session state after successful submission
                if "current_price" in st.session_state:
                    del st.session_state.current_price
            except Exception as e:
                st.error(f"Error during calculations or saving: {e}")
def show_matrix():
    st.header("📋 Portfolio Matrix View")
    
    with st.container():
        st.markdown("""
        <div class="card">
            <p style="margin-bottom: 0; color: var(--secondary);">
                Visual overview of your portfolio performance. Click on each stock to see details.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    df = load_data()
    df = df.dropna(how="all")

    if df.empty:
        st.warning("No portfolio data found. Add some stocks first!")
    else:
        holding_df = df[df["Holding"] == 1]
        if holding_df.empty:
            st.info("No active holdings found (filtered for 'Holding' == 1).")
        else:
            total_value = holding_df["Current value"].sum()
            total_investment = holding_df["Buy value"].sum()
            total_profit = total_value - total_investment
            profit_percent = (total_profit / total_investment) * 100 if total_investment else 0
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Value", f"${total_value:,.2f}")
            with col2:
                st.metric("Total Invested", f"${total_investment:,.2f}")
            with col3:
                st.metric("Total Profit/Loss", f"${total_profit:,.2f}", 
                         f"{profit_percent:.2f}%",
                         delta_color="inverse" if total_profit < 0 else "normal")
            with col4:
                st.metric("Number of Holdings", len(holding_df))
            
            st.subheader("Your Holdings")
            
            # Add CSS for the grid
            st.markdown("""
            <style>
                .metric-grid {
                    display: grid;
                    grid-template-columns: repeat(3, 1fr);
                    gap: 1px;
                    background-color: #e0e0e0;
                    padding: 1px;
                    border-radius: 8px;
                    margin-bottom: 10px;
                }
                .metric-header {
                    background-color: #f8f9fa;
                    padding: 8px;
                    text-align: center;
                    font-weight: bold;
                    border-bottom: 1px solid #e0e0e0;
                }
                .metric-value {
                    background-color: white;
                    padding: 10px;
                    text-align: center;
                }
                .positive {
                    color: #28a745;
                }
                .negative {
                    color: #dc3545;
                }
            </style>
            """, unsafe_allow_html=True)
            
            for _, row in holding_df.iterrows():
                with st.expander(f"{row['Ticker']} - ${row['Current stock price']:.2f} ({row['% up/down']:.2f}%)"):
                    # First row of metrics
                    st.markdown("""
                    <div class="metric-grid">
                        <div class="metric-header">Shares</div>
                        <div class="metric-header">Current Price</div>
                        <div class="metric-header">Profit/Loss</div>
                        <div class="metric-value">{shares}</div>
                        <div class="metric-value">${current_price:.2f}</div>
                        <div class="metric-value {profit_class}">${profit:.2f}</div>
                    </div>
                    """.format(
                        shares=row['# of shares'],
                        current_price=row['Current stock price'],
                        profit=row['$ up/down'],
                        profit_class="positive" if float(row['$ up/down']) >= 0 else "negative"
                    ), unsafe_allow_html=True)
                    
                    # Second row of metrics
                    st.markdown("""
                    <div class="metric-grid">
                        <div class="metric-header">Buy Price</div>
                        <div class="metric-header">% Change</div>
                        <div class="metric-header">Stop Loss</div>
                        <div class="metric-value">${buy_price:.2f}</div>
                        <div class="metric-value {pct_class}">{pct_change:.2f}%</div>
                        <div class="metric-value">${stop_loss:.2f}</div>
                    </div>
                    """.format(
                        buy_price=row['Buy stock price'],
                        pct_change=row['% up/down'],
                        pct_class="positive" if float(row['% up/down']) >= 0 else "negative",
                        stop_loss=row['Stop Loss']
                    ), unsafe_allow_html=True)
                    
                    # Third row of metrics
                    st.markdown("""
                    <div class="metric-grid">
                        <div class="metric-header">Stop Loss %</div>
                        <div class="metric-header">Days Held</div>
                        <div class="metric-header">Remark</div>
                        <div class="metric-value {sl_class}">{sl_pct:.2f}%</div>
                        <div class="metric-value">{days}</div>
                        <div class="metric-value">{remark}</div>
                    </div>
                    """.format(
                        sl_pct=row['Stop_loss_%'],
                        sl_class="positive" if float(row['Stop_loss_%']) >= 0 else "negative",
                        days=row['Days'],
                        remark=row['Remark'] if pd.notna(row['Remark']) else 'N/A'
                    ), unsafe_allow_html=True)
def show_dashboard():
    st.header("📈 Portfolio Dashboard")
    
    with st.container():
        st.markdown("""
        <div class="card">
            <p style="margin-bottom: 0; color: var(--secondary);">
                Comprehensive overview of your portfolio performance and analytics.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    df = load_data()
    if df.empty:
        st.warning("No data available")
        return
    
    total_investment = df["Buy value"].sum()
    current_value = df["Current value"].sum()
    total_profit = current_value - total_investment
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Investment", f"${total_investment:,.2f}")
    with col2:
        st.metric("Current Value", f"${current_value:,.2f}")
    with col3:
        st.metric("Total Profit/Loss", f"${total_profit:,.2f}", 
                 f"{((current_value - total_investment)/total_investment)*100:.2f}%")
    
    st.subheader("Performance by Stock")
    performance_df = df[['Ticker', '% up/down', '$ up/down']].sort_values('% up/down', ascending=False)
    st.bar_chart(performance_df.set_index('Ticker')['% up/down'])

def main():
    # Sidebar setup
    with st.sidebar:
        st.markdown("""
        <div style="padding: 10px; background: linear-gradient(135deg, #4f8bf9, #2c3e50); 
                    border-radius: 10px; margin-bottom: 20px;">
            <h2 style="color: white; margin-bottom: 0;">📄 Connect Google Sheet</h2>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div style="background: rgba(255,255,255,0.1); padding: 15px; border-radius: 8px; margin-bottom: 20px;">
            <p style="color: white; margin-bottom: 5px;">1. <b>Enter your Google Sheet details</b></p>
            <p style="color: white; margin-bottom: 5px;">2. <b>Share with service account</b></p>
            <p style="color: white; margin-bottom: 0;">3. <b>Start tracking your portfolio</b></p>
        </div>
        """, unsafe_allow_html=True)
        
        sheet_name = st.text_input("📘 Sheet Name", help="The name of your Google Spreadsheet")
        worksheet_name = st.text_input("📄 Worksheet Name", value="Sheet1", 
                                     help="The specific worksheet/tab name within your spreadsheet")
        
        st.markdown("""
        <div style="background: rgba(255,255,255,0.1); padding: 15px; border-radius: 8px; margin-top: 20px;">
            <p style="color: white; margin-bottom: 10px;"><b>Share your sheet with:</b></p>
            <code style="background: rgba(0,0,0,0.2); color: white; padding: 5px 10px; border-radius: 4px; display: block;">
                your-service-account@your-project.iam.gserviceaccount.com
            </code>
            <p style="color: white; font-size: 0.8em; margin-top: 5px;">(Editor permissions required)</p>
        </div>
        """, unsafe_allow_html=True)

    if not (sheet_name and worksheet_name):
        st.warning("⚠️ Enter your Google Sheet info to begin.")
        return

    st.session_state["sheet_name"] = sheet_name
    st.session_state["worksheet"] = worksheet_name
    st.session_state["creds"] = "creds.json"

    st.title("📈 Stock Portfolio Tracker")
    st.markdown("""
    <div style="background: linear-gradient(135deg, #f5f7fa, #e4e8eb); padding: 20px; 
                border-radius: 10px; margin-bottom: 30px;">
        <p style="margin-bottom: 0; font-size: 1.1rem;">
            Track your investments, monitor performance, and manage your stock portfolio with ease.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Navigation cards
    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container():
            st.markdown("""
            <div class="metric-card">
                <h3 style="margin-top: 0;">➕ Add New Entry</h3>
                <p>Add a new stock to your portfolio</p>
                <div style="text-align: right;">
            """, unsafe_allow_html=True)
            if st.button("Go to Add Entry", key="add_entry_btn"):
                st.session_state.page = "add_entry"
            st.markdown("</div></div>", unsafe_allow_html=True)
    
    with col2:
        with st.container():
            st.markdown("""
            <div class="metric-card">
                <h3 style="margin-top: 0;">📋 Display Matrix</h3>
                <p>View your portfolio performance</p>
                <div style="text-align: right;">
            """, unsafe_allow_html=True)
            if st.button("Go to Matrix", key="matrix_btn"):
                st.session_state.page = "display_matrix"
            st.markdown("</div></div>", unsafe_allow_html=True)
    
    with col3:
        with st.container():
            st.markdown("""
            <div class="metric-card">
                <h3 style="margin-top: 0;">📈 Dashboard</h3>
                <p>Analytics and charts</p>
                <div style="text-align: right;">
            """, unsafe_allow_html=True)
            if st.button("Go to Dashboard", key="dashboard_btn"):
                st.session_state.page = "dashboard"
            st.markdown("</div></div>", unsafe_allow_html=True)

    # Page routing
    if "page" not in st.session_state:
        st.session_state.page = None
    
    if st.session_state.page == "add_entry":
        show_add_entry()
    elif st.session_state.page == "display_matrix":
        show_matrix()
    elif st.session_state.page == "dashboard":
        show_dashboard()
    else:
        st.info("👈 Select an action from the cards above to get started")

if __name__ == "__main__":
    main()
