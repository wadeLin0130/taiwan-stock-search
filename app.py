import yfinance as yf
import pandas as pd
import csv
import os
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta

# 設定網頁標題與排版
st.set_page_config(page_title="台股 K 線型態搜尋器", layout="wide")

# 初始化 Session State，用於狀態管理
if 'pattern_str' not in st.session_state:
    st.session_state.pattern_str = "漲漲跌漲"

if 'df_result' not in st.session_state:
    st.session_state.df_result = None

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

def get_colored_sequence_html(seq, up_color, down_color, flat_color):
    """將文字序列轉換為帶有顏色與間隔的 HTML 格式"""
    res = []
    for char in seq:
        if char == '漲':
            res.append(f'<span style="color:{up_color}; font-weight:bold; margin-right:12px; font-size:18px;">漲</span>')
        elif char == '跌':
            res.append(f'<span style="color:{down_color}; font-weight:bold; margin-right:12px; font-size:18px;">跌</span>')
        else:
            res.append(f'<span style="color:{flat_color}; font-weight:bold; margin-right:12px; font-size:18px;">平</span>')
    return "".join(res)

@st.cache_data(ttl=timedelta(hours=12), show_spinner=False)
def download_stock_data(symbols, period, timeframe):
    try:
        data = yf.download(
            tickers=symbols, 
            period=period, 
            interval=timeframe, 
            group_by='ticker', 
            threads=10, 
            progress=False
        )
        return data
    except Exception as e:
        st.error(f"下載過程發生錯誤: {str(e)}")
        return pd.DataFrame()

def main():
    st.title("台股歷史 K 線型態搜尋器")
    st.markdown("設定好指定的 K 棒顏色序列，程式將自動匹配出符合該型態的台股標的。點擊搜尋結果即可查看互動式 K 線圖。")

    stock_symbols = load_stock_symbols('tw_stocks.csv')
    if not stock_symbols:
        st.warning("找不到 tw_stocks.csv，將使用內建示範名單進行測試。")
        stock_symbols = ['2330.TW', '2317.TW', '2454.TW', '3105.TWO', '3293.TWO', '8046.TW', '3017.TW', '2603.TW', '6239.TW', '2882.TW']

    with st.sidebar:
        st.header("搜尋條件設定")
        
        # 顏色配置切換
        color_scheme = st.radio(
            "K 線顏色配置 (影響文字與圖表)",
            ["紅漲綠跌 (台灣習慣)", "綠漲紅跌 (國際習慣)"]
        )
        
        if "紅漲" in color_scheme:
            up_color, down_color, flat_color = "#FF3333", "#00CC00", "#999999"
        else:
            up_color, down_color, flat_color = "#00CC00", "#FF3333", "#999999"

        st.divider()

        st.subheader("尋找型態")
        st.text_input("輸入型態字串", key="pattern_str")
        
        cols = st.columns(5)
        with cols[0]: st.button("漲", on_click=update_pattern, args=("append", "漲"))
        with cols[1]: st.button("跌", on_click=update_pattern, args=("append", "跌"))
        with cols[2]: st.button("平", on_click=update_pattern, args=("append", "平"))
        with cols[3]: st.button("退格", on_click=update_pattern, args=("backspace",))
        with cols[4]: st.button("清空", on_click=update_pattern, args=("clear",))
        
        # 視覺化預覽目前的搜尋字串
        st.markdown("目標型態預覽：")
        st.markdown(get_colored_sequence_html(st.session_state.pattern_str, up_color, down_color, flat_color), unsafe_allow_html=True)
        
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
            
            if matched_stocks:
                st.session_state.df_result = pd.DataFrame(matched_stocks)
            else:
                st.session_state.df_result = pd.DataFrame()

    # 呈現搜尋結果與圖表互動邏輯
    if st.session_state.df_result is not None:
        if not st.session_state.df_result.empty:
            st.success(f"搜尋完成。共找到 {len(st.session_state.df_result)} 檔符合條件的股票。請在下方表格點擊任一列來查看 K 線圖。")
            
            # 使用 Streamlit 原生表格的單列選取功能
            selection_event = st.dataframe(
                st.session_state.df_result, 
                use_container_width=True,
                selection_mode="single-row",
                on_select="rerun",
                column_config={
                    "股票代號": st.column_config.TextColumn("股票代號"),
                    "最新收盤價": st.column_config.NumberColumn("最新收盤價", format="%.2f"),
                    "近期K線序列": st.column_config.TextColumn("近期K線序列"),
                    "匹配位置": st.column_config.NumberColumn("匹配位置")
                },
                hide_index=True
            )

            # 若使用者點擊了某個股票，則渲染該股票的一年期互動圖表
            if selection_event.selection.rows:
                selected_idx = selection_event.selection.rows[0]
                selected_row = st.session_state.df_result.iloc[selected_idx]
                selected_symbol = selected_row["股票代號"]
                matched_sequence = selected_row["近期K線序列"]

                st.markdown("---")
                st.subheader(f"{selected_symbol} 走勢分析與特徵核對")
                st.markdown(f"**匹配序列：** {get_colored_sequence_html(matched_sequence, up_color, down_color, flat_color)}", unsafe_allow_html=True)
                
                with st.spinner("正在載入近一年歷史資料..."):
                    # 改用 yf.Ticker().history() 確保單一標的的回傳格式為平坦結構
                    ticker = yf.Ticker(selected_symbol)
                    chart_df = ticker.history(period="1y", interval="1d")

                    if not chart_df.empty and 'Open' in chart_df.columns and 'Close' in chart_df.columns:
                        chart_df = chart_df.dropna(subset=['Open', 'Close'])
                    else:
                        chart_df = pd.DataFrame()

                    if not chart_df.empty:
                        # 建立 Plotly 互動式 K 線圖
                        fig = go.Figure(data=[go.Candlestick(
                            x=chart_df.index,
                            open=chart_df['Open'], high=chart_df['High'],
                            low=chart_df['Low'], close=chart_df['Close'],
                            increasing_line_color=up_color, decreasing_line_color=down_color
                        )])
                        
                        fig.update_layout(
                            title=f"{selected_symbol} 近一年日線走勢 (支援滾動縮放)",
                            xaxis_rangeslider_visible=True,
                            height=550,
                            margin=dict(l=0, r=0, t=50, b=0)
                        )
                        
                        # 隱藏週末的空白區間
                        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
                        
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("無法取得此標的的歷史資料供繪圖。")
        else:
            st.info("條件過濾後，未找到完全符合型態的股票。您可以嘗試縮短型態字串或放寬股價限制。")

if __name__ == "__main__":
    main()
