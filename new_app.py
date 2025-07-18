import os
import json

# Write creds.json dynamically from env variable (Render/Railway-safe)
if not os.path.exists("creds.json") and "GCP_CREDENTIALS" in os.environ:
    with open("creds.json", "w") as f:
        json.dump(json.loads(os.environ["GCP_CREDENTIALS"]), f)

import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials
from gspread_formatting import format_cell_ranges, cellFormat, color

# Google Sheets setup

# Google Sheets connection
def connect_to_gsheet():
    if "creds" not in st.session_state or "sheet_name" not in st.session_state or "worksheet" not in st.session_state:
        return None  # suppress warning during deployment
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
        apply_formatting(sheet)
    except Exception as e:
        st.error(f"Error saving to Google Sheet: {e}")

# Apply conditional formatting to Google Sheet
def apply_formatting(sheet):
    try:
        from gspread_formatting import (
            CellFormat, color, textFormat,
            format_cell_range, ConditionalFormatRule,
            BooleanRule, BooleanCondition,
            get_conditional_format_rules, GridRange
        )

        # Bold header row and background
        header_fmt = CellFormat(
            textFormat=textFormat(bold=True),
            backgroundColor=color(0.9, 0.9, 0.9)
        )
        format_cell_range(sheet, 'A1:Z1', header_fmt)

        # Increase column widths for better visibility
        sheet.format('A:Z', {'wrapStrategy': 'WRAP'})
        sheet.resize(rows=200, cols=20)

        # Bold Ticker column
        ticker_fmt = CellFormat(textFormat=textFormat(bold=True))
        format_cell_range(sheet, 'A2:A100', ticker_fmt)

        # Conditional formatting for $ up/down (G column)
        sheet_id = sheet._properties['sheetId']
        rules = get_conditional_format_rules(sheet)
        rules.clear()

        rules.append(ConditionalFormatRule(
            ranges=[GridRange(sheetId=sheet_id, startRowIndex=1, endRowIndex=100, startColumnIndex=6, endColumnIndex=7)],
            booleanRule=BooleanRule(
                condition=BooleanCondition('NUMBER_GREATER', ['0']),
                format=CellFormat(backgroundColor=color(0.85, 1, 0.85))
            )
        ))

        rules.append(ConditionalFormatRule(
            ranges=[GridRange(sheetId=sheet_id, startRowIndex=1, endRowIndex=100, startColumnIndex=6, endColumnIndex=7)],
            booleanRule=BooleanRule(
                condition=BooleanCondition('NUMBER_LESS', ['0']),
                format=CellFormat(backgroundColor=color(1, 0.85, 0.85))
            )
        ))

                # Zebra striping (alternate row shading)
        rules.append(ConditionalFormatRule(
            ranges=[GridRange(sheetId=sheet_id, startRowIndex=1, endRowIndex=100, startColumnIndex=0, endColumnIndex=15)],
            booleanRule=BooleanRule(
                condition=BooleanCondition('CUSTOM_FORMULA', ['=ISEVEN(ROW())']),
                format=CellFormat(backgroundColor=color(0.97, 0.97, 0.97))
            )
        ))

        # Highlight all percentage columns with green if gain, red if loss
        percent_columns = [(7, 8), (8, 9), (9, 10), (13, 14), (14, 15)]  # % up/down, Stop_loss_%, Profit%_Portfolio, Stoploss_Portfolio%
        for start_col, end_col in percent_columns:
            rules.append(ConditionalFormatRule(
                ranges=[GridRange(sheetId=sheet_id, startRowIndex=1, endRowIndex=100, startColumnIndex=start_col, endColumnIndex=end_col)],
                booleanRule=BooleanRule(
                    condition=BooleanCondition('NUMBER_GREATER', ['0']),
                    format=CellFormat(backgroundColor=color(0.85, 1, 0.85))
                )
            ))
            rules.append(ConditionalFormatRule(
                ranges=[GridRange(sheetId=sheet_id, startRowIndex=1, endRowIndex=100, startColumnIndex=start_col, endColumnIndex=end_col)],
                booleanRule=BooleanRule(
                    condition=BooleanCondition('NUMBER_LESS', ['0']),
                    format=CellFormat(backgroundColor=color(1, 0.85, 0.85))
                )
            ))

        rules.save()
        sheet.freeze(rows=1)

    except Exception as e:
        st.warning(f"⚠️ Could not apply full formatting: {e}")

def get_current_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")
        if not hist.empty:
            return round(hist["Close"].iloc[-1], 2)
        else:
            st.warning("No historical data found for the ticker.")
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
        else:
            return None
    except Exception:
        return None

def main():
    # Sidebar setup (sheet name only)
    st.sidebar.title("📄 Connect Your Google Sheet")
    st.sidebar.markdown(
        """
        1. **Enter your Google Sheet name**  
        2. **Enter the worksheet name**  
        3. 📨 **Share your Google Sheet** with this email:

        ```
        your-service-account@your-project.iam.gserviceaccount.com
        ```

        Give **Editor** access so updates work properly.
        """
    )

    sheet_name = st.sidebar.text_input("📘 Sheet Name")
    worksheet_name = st.sidebar.text_input("📄 Worksheet Name", value="Sheet1")

    if sheet_name and worksheet_name:
        st.session_state["sheet_name"] = sheet_name
        st.session_state["worksheet"] = worksheet_name
        st.session_state["creds"] = "creds.json"  # Hardcoded
        st.success("✅ Using developer's service account. Please ensure your sheet is shared with the service account email.")
    else:
        st.warning("⚠️ Enter your Google Sheet info to begin.")
        return

    st.title("📈 Stock Tracker App")

    # Display existing data before form
    existing_df = load_data()
    if not existing_df.empty:
        existing_df["B_Date"] = pd.to_datetime(existing_df["B_Date"], errors='coerce')
        existing_df["Days"] = existing_df["B_Date"].apply(lambda d: (datetime.today().date() - d.date()).days if pd.notnull(d) and hasattr(d, 'date') else '')
        st.subheader("📊 Current Portfolio Data")
        st.dataframe(existing_df, use_container_width=True)


    ticker = st.text_input("Stock Ticker (e.g., AAPL)")
    shares = st.number_input("Number of Shares", min_value=1, step=1)
    buy_price = st.number_input("Buy Stock Price", min_value=0.0, format="%.2f")
    stop_loss = st.number_input("Stop Loss Price", min_value=0.0, format="%.2f")

    # Additional Inputs
    pur_spy = st.number_input("Enter SPY Purchase Price (Pur_Spy)", min_value=0.0, format="%.2f")
    remark = st.text_input("Remark")

    current_price = get_current_price(ticker) if ticker else None

    if ticker and current_price:
        st.success(f"Current stock price of {ticker.upper()}: ${current_price}")

    if pur_spy and get_current_spy():
        st.success(f"Current SPY price: ${get_current_spy()}")

    if st.button("Add Entry") and ticker and current_price:
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
            days_held = (today - today).days  # placeholder, will recalc later
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

            # Remove any old total rows again to be safe
            df = df[df["Ticker"] != "Total"]

            # Ensure required columns exist
            for col in ["Profit%_Portfolio", "Stoploss_Portfolio%"]:
                if col not in df.columns:
                    df[col] = 0.0

            # Calculate totals
            total_up_down = df["$ up/down"].astype(float).sum()
            total_sl_profit = df["Stop Loss Profit"].astype(float).sum()

            # Compute portfolio percentage contributions
            df["Profit%_Portfolio"] = df["$ up/down"].apply(
                lambda x: round((float(x) / total_up_down) * 100, 2) if total_up_down else 0
            )
            df["Stoploss_Portfolio%"] = df["Stop Loss Profit"].apply(
                lambda x: round((float(x) / total_sl_profit) * 100, 2) if total_sl_profit else 0
            )

            # Create total row
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

        except Exception as e:
            st.error(f"Error during calculations or saving: {e}")

if __name__ == "__main__":
    main()
