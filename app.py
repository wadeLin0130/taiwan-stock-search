import yfinance as yf
import pandas as pd
import csv
import os
import streamlit as st
from datetime import datetime, timedelta

# 設定網頁標題與排版
st.set_page_config(page_title="台股 K 線型態搜尋器", layout="wide")

# 初始化 Session State，用於快捷按鈕的文字狀態管理
if 'pattern_str' not in st.session_state:
    st.session_state.pattern_str = "漲漲跌漲"

def update_pattern(action, char=""):
    if action == "append":
        st.session_state.pattern_str += char
    elif action == "backspace":
        st.session_state.pattern_str = st.session_state.pattern_str[:-1]
    elif action == "clear":
        st.session_state.pattern_str = ""

def load_stock_symbols(file_path):
    symbols = []
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 2: continue
                symbol = str(row[0]).strip()
                market = str(row[1]).strip()
                if not symbol or not symbol[0].isdigit(): continue
                
                if '上市' in market:
                    symbols.append(f"{symbol}.TW")
                elif '櫃' in market or 'OTC' in market.upper():
                    symbols.append(f"{symbol}.TWO")
                else:
                    symbols.append(f"{symbol}.TW")
    except Exception:
        pass
    return symbols

def get_kline_color(open_price, close_price):
    if close_price > open_price: return '漲'
    elif close_price < open_price: return '跌'
    else: return '平'

# 使用 Streamlit 內建的強大快取機制，設定 12 小時過期 (ttl)
@st.cache_data(ttl=timedelta(hours=12), show_spinner=False)
def download_stock_data(symbols, period, timeframe):
    try:
        # 雲端 Linux 伺服器無 macOS 的嚴格連線限制，開啟 threads=10 以最大化下載速度
        # 同時避免設定過高導致 Yahoo Finance IP 封鎖
        data = yf.download(
            tickers=symbols, 
            period=period, 
            interval=timeframe, 
            group_by='ticker', 
            threads=30, 
            progress=False
        )
        return data
    except Exception as e:
        st.error(f"下載過程發生錯誤: {str(e)}")
        return pd.DataFrame()

def main():
    st.title("台股歷史 K 線型態搜尋器")
    st.markdown("設定好指定的 K 棒顏色序列，程式將自動匹配出符合該型態的台股標的。")

    # 讀取股票清單
    stock_symbols = load_stock_symbols('tw_stocks.csv')
    if not stock_symbols:
        st.warning("找不到 tw_stocks.csv，將使用內建示範名單進行測試。")
        stock_symbols = ['2330.TW', '2317.TW', '2454.TW', '3105.TWO', '3293.TWO', '8046.TW', '3017.TW', '2603.TW', '6239.TW', '2882.TW']

    # UI：側邊欄設定參數
    with st.sidebar:
        st.header("搜尋條件設定")
        
        # 快捷按鈕區塊
        st.subheader("尋找型態")
        st.text_input("輸入型態字串", key="pattern_str")
        
        cols = st.columns(5)
        with cols[0]: st.button("漲", on_click=update_pattern, args=("append", "漲"))
        with cols[1]: st.button("跌", on_click=update_pattern, args=("append", "跌"))
        with cols[2]: st.button("平", on_click=update_pattern, args=("append", "平"))
        with cols[3]: st.button("退格", on_click=update_pattern, args=("backspace",))
        with cols[4]: st.button("清空", on_click=update_pattern, args=("clear",))
        
        st.divider()
        
        timeframe_raw = st.selectbox("K線週期", ["日線 (1d)", "週線 (1wk)", "月線 (1mo)"])
        if "1d" in timeframe_raw:
            timeframe, period = "1d", "6mo"
        elif "1wk" in timeframe_raw:
            timeframe, period = "1wk", "2y"
        else:
            timeframe, period = "1mo", "5y"
            
        lookback_bars = st.number_input("最新K棒數 (檢查範圍)", min_value=5, max_value=100, value=20)
        min_price = st.number_input("最低股價", min_value=0.0, value=10.0)
        max_price = st.number_input("最高股價", min_value=0.0, value=1000.0)
        
        start_search = st.button("開始搜尋", type="primary", use_container_width=True)

    # 核心邏輯處理
    if start_search:
        target_pattern = st.session_state.pattern_str.strip()
        
        if not target_pattern:
            st.error("請輸入欲尋找的型態。")
            return

        with st.spinner('正在從 Yahoo Finance 獲取資料 (初次下載約需數十秒，後續具備 12 小時快取)...'):
            data = download_stock_data(stock_symbols, period, timeframe)

        if data.empty:
            st.error("資料獲取失敗或無資料回傳。")
            return

        with st.spinner('資料載入完畢，正在進行特徵比對...'):
            matched_stocks = []
            
            for symbol in stock_symbols:
                try:
                    if isinstance(data.columns, pd.MultiIndex):
                        if symbol in data.columns.levels[0]:
                            df = data[symbol].copy()
                        else: continue
                    else:
                        if len(stock_symbols) == 1 or symbol == stock_symbols[0]:
                            df = data.copy()
                        else: continue
                        
                    if 'Open' not in df.columns or 'Close' not in df.columns: continue
                    
                    df = df.dropna(subset=['Open', 'Close'])
                    if df.empty or len(df) < lookback_bars: continue
                        
                    df = df.tail(lookback_bars)
                    latest_close = float(df['Close'].iloc[-1])
                    
                    if not (min_price <= latest_close <= max_price): continue
                        
                    colors = [get_kline_color(float(row['Open']), float(row['Close'])) for _, row in df.iterrows()]
                    color_sequence = "".join(colors)
                    
                    if target_pattern in color_sequence:
                        matched_stocks.append({
                            '股票代號': symbol,
                            '最新收盤價': round(latest_close, 2),
                            '近期K線序列': color_sequence,
                            '匹配位置': color_sequence.find(target_pattern) + 1
                        })
                except Exception:
                    continue
            
            # 結果呈現
            if matched_stocks:
                st.success(f"搜尋完成。共找到 {len(matched_stocks)} 檔符合條件的股票。")
                df_result = pd.DataFrame(matched_stocks)
                # 使用 Streamlit 內建的 DataFrame 元件，直接支援點擊標題正倒序排序
                st.dataframe(
                    df_result, 
                    use_container_width=True,
                    column_config={
                        "股票代號": st.column_config.TextColumn("股票代號"),
                        "最新收盤價": st.column_config.NumberColumn("最新收盤價", format="%.2f"),
                        "近期K線序列": st.column_config.TextColumn("近期K線序列"),
                        "匹配位置": st.column_config.NumberColumn("匹配位置")
                    },
                    hide_index=True
                )
            else:
                st.info("條件過濾後，未找到完全符合型態的股票。您可以嘗試縮短型態字串或放寬股價限制。")

if __name__ == "__main__":
    main()
