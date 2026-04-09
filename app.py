import yfinance as yf
import pandas as pd
import csv
import os
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta

# 設定網頁標題與排版
st.set_page_config(page_title="台股歷史 K 棒組合搜尋工具", layout="wide")

# 初始化 Session State，用於狀態管理
if 'pattern_str' not in st.session_state:
    st.session_state.pattern_str = "跌跌跌跌漲漲漲跌跌"

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
    """將文字序列轉換為帶有顏色與間距的 HTML 格式，提升視覺辨識度"""
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
def download_stock_data_chunked(symbols, period, timeframe):
    """分批下載並提供進度條，回傳以股票代號為鍵值的字典，避免索引錯亂"""
    progress_text = "正在從 Yahoo Finance 下載資料"
    progress_bar = st.progress(0, text=f"{progress_text} (初始化中...)")
    chunk_size = 50
    total = len(symbols)
    
    result_dict = {}
    for i in range(0, total, chunk_size):
        chunk = symbols[i:i+chunk_size]
        try:
            data = yf.download(
                tickers=chunk, 
                period=period, 
                interval=timeframe, 
                group_by='ticker', 
                threads=10, 
                progress=False
            )
            # 將下載的大表拆解為獨立 DataFrame 並存入字典
            if isinstance(data.columns, pd.MultiIndex):
                for sym in chunk:
                    if sym in data.columns.levels[0]:
                        df = data[sym].copy()
                        if not df.empty:
                            result_dict[sym] = df
            else:
                if len(chunk) == 1:
                    sym = chunk[0]
                    result_dict[sym] = data.copy()
        except Exception:
            pass
        
        current_count = min(total, i + chunk_size)
        progress_bar.progress(current_count / total, text=f"{progress_text} ({current_count}/{total})")
    
    progress_bar.empty()
    return result_dict

def main():
    st.title("台股歷史 K 棒組合搜尋工具")
    st.markdown("設定好指定的 K 棒顏色組合，搜尋符合該組合的台股標的。破解分析師蓋牌。")

    stock_symbols = load_stock_symbols('tw_stocks.csv')
    if not stock_symbols:
        st.warning("找不到 tw_stocks.csv，將使用內建示範名單進行測試。")
        stock_symbols = ['2330.TW', '2317.TW', '2454.TW', '3105.TWO', '3293.TWO', '8046.TW', '3017.TW', '2603.TW', '6239.TW', '2882.TW']

    with st.sidebar:
        st.header("搜尋條件設定")
        
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
            st.error("請輸入欲尋找的Ｋ棒組合。")
            return

        # 取得資料 (有快取時進度條會瞬間跑完)
        data_dict = download_stock_data_chunked(stock_symbols, period, timeframe)

        if not data_dict:
            st.error("資料獲取失敗或無資料回傳。")
            return

        matched_stocks = []
        progress_text = "正在比對特徵"
        progress_bar = st.progress(0, text=f"{progress_text} (0/{len(stock_symbols)})")
        total_symbols = len(stock_symbols)
        
        for i, symbol in enumerate(stock_symbols):
            if i % 20 == 0:
                progress_bar.progress(i / total_symbols, text=f"{progress_text} ({i}/{total_symbols})")
                
            df = data_dict.get(symbol)
            if df is None or df.empty: continue
                
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
                
        progress_bar.empty()
        
        if matched_stocks:
            st.session_state.df_result = pd.DataFrame(matched_stocks)
        else:
            st.session_state.df_result = pd.DataFrame()

    if st.session_state.df_result is not None:
        if not st.session_state.df_result.empty:
            st.success(f"搜尋完成。共找到 {len(st.session_state.df_result)} 檔符合條件的股票。打勾看K線圖")
            
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

            if selection_event.selection.rows:
                selected_idx = selection_event.selection.rows[0]
                selected_row = st.session_state.df_result.iloc[selected_idx]
                selected_symbol = selected_row["股票代號"]
                matched_sequence = selected_row["近期K線序列"]
                target_pattern = st.session_state.pattern_str.strip()
                position = selected_row["匹配位置"]

                st.markdown("---")
                st.subheader(f"{selected_symbol} 走勢分析與特徵核對")
                st.markdown(f"**匹配序列：** {get_colored_sequence_html(matched_sequence, up_color, down_color, flat_color)}", unsafe_allow_html=True)
                
                # 直接沿用已在記憶體中的資料，大幅減少載入延遲
                # 需要重新呼叫快取函數取得完整字典 (會瞬間回傳)
                data_dict = download_stock_data_chunked(stock_symbols, period, timeframe)
                chart_df = data_dict.get(selected_symbol)

                if chart_df is not None and not chart_df.empty:
                    chart_df = chart_df.dropna(subset=['Open', 'Close'])
                    
                    lookback_df = chart_df.tail(lookback_bars)
                    x_min = lookback_df.index[0]
                    x_max = lookback_df.index[-1]
                    
                    # 計算匹配區間的起訖時間
                    match_start_idx = position - 1
                    match_end_idx = match_start_idx + len(target_pattern) - 1
                    highlight_start = lookback_df.index[match_start_idx]
                    highlight_end = lookback_df.index[match_end_idx]

                    fig = go.Figure(data=[go.Candlestick(
                        x=chart_df.index,
                        open=chart_df['Open'], high=chart_df['High'],
                        low=chart_df['Low'], close=chart_df['Close'],
                        increasing_line_color=up_color, decreasing_line_color=down_color,
                        increasing_fillcolor=up_color, decreasing_fillcolor=down_color
                    )])
                    
                    # 加入半透明方塊，標示出吻合的特徵區域
                    fig.add_vrect(
                        x0=highlight_start, x1=highlight_end,
                        fillcolor="rgba(135, 206, 250, 0.4)",
                        layer="below",
                        line_width=2,
                        line_color="rgba(135, 206, 250, 1)",
                        annotation_text=" 匹配位置",
                        annotation_position="top left",
                        annotation_font=dict(color="#1f77b4", size=14, weight="bold")
                    )
                    
                    fig.update_layout(
                        title=f"{selected_symbol} 歷史走勢 (已縮放至近期 {lookback_bars} 根，可滑動查看完整歷史)",
                        xaxis_rangeslider_visible=True,
                        height=550,
                        margin=dict(l=0, r=0, t=50, b=0)
                    )
                    
                    rangebreaks = []
                    if timeframe == '1d':
                        rangebreaks.append(dict(bounds=["sat", "mon"]))
                    
                    # 強制設定 X 軸預設顯示範圍為搜尋指定的 K 棒數
                    fig.update_xaxes(
                        range=[x_min, x_max],
                        rangebreaks=rangebreaks
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("無法取得此標的的歷史資料供繪圖。")
        else:
            st.info("條件過濾後，未找到完全符合型態的股票。您可以嘗試縮短型態字串或放寬股價限制。")

if __name__ == "__main__":
    main()
