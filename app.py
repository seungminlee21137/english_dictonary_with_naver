import streamlit as st
import requests
import json
import re
import os

# --------------------------------------------------------------------------
# 1. 데이터 관리
# --------------------------------------------------------------------------
DATA_FILE = "my_dictionary_data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"history": [], "favorites": []}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"history": [], "favorites": []}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --------------------------------------------------------------------------
# 2. 유틸리티 함수
# --------------------------------------------------------------------------
def set_keyword(keyword):
    st.session_state['search_input'] = keyword
    st.session_state['search_widget'] = keyword

def on_history_change():
    selected = st.session_state.get('history_dropdown')
    if selected and selected != "🔍 검색 기록 선택...":
        st.session_state['search_widget'] = selected
        st.session_state['search_input'] = selected

# --------------------------------------------------------------------------
# 3. 크롤링 로직
# --------------------------------------------------------------------------
def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html)

def extract_values_deeply(data):
    results = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k == 'value' and isinstance(v, str) and v.strip():
                results.append(clean_html(v))
            elif isinstance(v, str) and v.startswith('{') and ('"value"' in v or '"means"' in v):
                try:
                    inner_json = json.loads(v)
                    results.extend(extract_values_deeply(inner_json))
                except: pass
            else:
                results.extend(extract_values_deeply(v))
    elif isinstance(data, list):
        for item in data:
            results.extend(extract_values_deeply(item))
    return results

def extract_audio_deeply(data):
    if isinstance(data, dict):
        if 'searchPhoneticSymbolList' in data:
            return data['searchPhoneticSymbolList']
        for k, v in data.items():
            result = extract_audio_deeply(v)
            if result: return result
    elif isinstance(data, list):
        for item in data:
            result = extract_audio_deeply(item)
            if result: return result
    return None

def get_naver_data(keyword):
    url = f"https://en.dict.naver.com/api3/enko/search?query={keyword}&m=pc&lang=ko"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://en.dict.naver.com/",
    }
    result_dict = {"meanings": [], "audio": {"US": None, "GB": None}}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200: return result_dict
        full_data = response.json()
        all_found_values = extract_values_deeply(full_data)
        meaning_results = []
        for val in dict.fromkeys(all_found_values):
            if any(ord('가') <= ord(char) <= ord('힣') for char in val):
                if val != keyword: meaning_results.append(val)
        result_dict["meanings"] = meaning_results[:15]
        audio_list = extract_audio_deeply(full_data)
        if audio_list:
            for item in audio_list:
                s_type = str(item.get('symbolType', '')).upper()
                s_file = item.get('symbolFile', '')
                if s_file and s_file.startswith("http://"): s_file = s_file.replace("http://", "https://")
                if s_file:
                    if 'US' in s_type or '미국' in s_type: result_dict["audio"]["US"] = s_file
                    elif 'GB' in s_type or '영국' in s_type: result_dict["audio"]["GB"] = s_file
    except: pass
    return result_dict

# --------------------------------------------------------------------------
# 4. Streamlit 화면 구성
# --------------------------------------------------------------------------
st.set_page_config(page_title="나만의 AI 영한사전", page_icon="🎧", layout="wide")

st.markdown("""
<style>
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    
    /* 메인 패딩 고정 */
    div[data-testid="stMainBlockContainer"], 
    div[data-testid="block-container"] {
        padding: 2rem !important;
        max-width: initial !important;
    }

    /* ------------------------------------------------------------------
       [핵심 수정] 사이드바 레이아웃 및 삭제 버튼 스타일링
       ------------------------------------------------------------------ */
       
    /* 1. 사이드바 Row(행) 레이아웃 재정의 */
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important; /* 줄바꿈 절대 금지 */
        align-items: center !important; /* 수직 중앙 */
        gap: 8px !important;
        width: 100% !important;
    }
    
    /* 2. 첫번째 컬럼 (단어 버튼) : 남은 공간 모두 차지 (Flex Grow) */
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] > div:first-child {
        flex: 1 1 auto !important; 
        min-width: 0 !important;   /* 텍스트 말줄임표 작동을 위한 필수 설정 */
        width: auto !important;
    }

    /* 3. 두번째 컬럼 (삭제 버튼) : 내용물 크기만큼만 (Flex Shrink 없음) */
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] > div:last-child {
        flex: 0 0 auto !important;
        width: auto !important;
        min-width: auto !important;
    }

    /* 4. 단어 버튼 스타일 */
    [data-testid="stSidebar"] div.stButton > button[kind="secondary"] {
        text-align: left;
        width: 100%;
        background-color: #f8f9fa;
        padding: 8px 10px;
        border: none;
        border-radius: 8px;
        font-size: 14px;
        margin: 0 !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    [data-testid="stSidebar"] div.stButton > button[kind="secondary"]:hover {
        background-color: #e9ecef; color: #03c75a;
    }

    /* 5. [수정됨] 삭제 버튼 스타일 (빨간색 & Compact) */
    /* 사이드바 안에 있는 primary 버튼만 타겟팅 */
    [data-testid="stSidebar"] button[kind="primary"] {
        background-color: #ff4b4b !important; /* 빨간색 배경 */
        border-color: #ff4b4b !important;
        color: white !important;
        padding: 0px 10px !important; /* 버튼 크기 줄임 */
        height: 38px !important;      /* 단어 버튼과 높이 맞춤 */
        line-height: 1 !important;
        margin: 0 !important;
        width: auto !important;
    }
    
    [data-testid="stSidebar"] button[kind="primary"]:hover {
        background-color: #ff3333 !important; /* 호버 시 더 진한 빨강 */
        border-color: #ff3333 !important;
    }
    
    /* 아이콘 내부 정렬 보정 */
    [data-testid="stSidebar"] button[kind="primary"] p {
        font-size: 16px !important;
        font-weight: bold !important;
        margin-bottom: 0px !important;
    }

    /* 기타 UI 요소 */
    div[data-testid="stAlert"] { padding: 2rem !important; border-radius: 12px !important; }
    
    button[kind="secondary"] { /* 메인화면 별표 버튼 */
        border: none !important; background: transparent !important; box-shadow: none !important;
        font-size: 24px !important; padding: 0 !important; margin-top: -10px !important;
    }
    button[kind="secondary"]:hover { color: #ffc107 !important; background: transparent !important; }

    .result-box {
        background-color: #ffffff; padding: 16px 20px; border-radius: 12px;
        border-left: 6px solid #03c75a; margin-bottom: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.08); font-size: 16px; line-height: 1.5;
    }
    div[data-testid="column"] button[kind="primary"] { margin-top: 0px; }
    [data-testid="stVerticalBlock"] { gap: 0.5rem !important; }

</style>
""", unsafe_allow_html=True)

# 초기화
if 'data' not in st.session_state:
    st.session_state['data'] = load_data()
if 'search_input' not in st.session_state:
    st.session_state['search_input'] = ""
if 'search_widget' not in st.session_state:
    st.session_state['search_widget'] = ""

# --- 사이드바 ---
with st.sidebar:
    st.header("⭐ 단어장")
    favorites = st.session_state['data']['favorites']
    favorites.sort(key=str.lower)
    
    if favorites:
        for fav_word in favorites:
            # 비율은 크게 중요하지 않음 (CSS flex가 처리)
            c1, c2 = st.columns([0.8, 0.2])
            with c1:
                # kind="secondary"를 명시하여 CSS 선택자가 정확히 잡도록 함
                st.button(f"📄 {fav_word}", key=f"fav_{fav_word}", on_click=set_keyword, args=(fav_word,), type="secondary")
            with c2:
                # kind="primary" (삭제 버튼 - CSS에서 빨간색 적용됨)
                if st.button("✕", key=f"fav_del_{fav_word}", type="primary"):
                    favorites.remove(fav_word)
                    st.session_state['data']['favorites'] = favorites
                    save_data(st.session_state['data'])
                    st.rerun()

# --- 메인 화면 ---
st.title("🎧 AI 영한사전")

# 검색창
col_search, col_btn = st.columns([0.8, 0.2], gap="small")
with col_search:
    user_query = st.text_input("검색어 입력", key="search_widget", label_visibility="collapsed", placeholder="단어를 입력하세요")
with col_btn:
    btn_click = st.button("검색", type="primary", use_container_width=True)

# 검색 기록
history = st.session_state['data']['history']
if history:
    sorted_history = sorted(history, key=str.lower)
    h_col1, h_col2 = st.columns([0.8, 0.2], gap="small")
    with h_col1:
        st.selectbox("최근 검색 기록", options=["🔍 검색 기록 선택..."] + sorted_history, key="history_dropdown", on_change=on_history_change, label_visibility="collapsed")
    with h_col2:
        if st.button("🗑️ 삭제", use_container_width=True):
            st.session_state['data']['history'] = []
            save_data(st.session_state['data'])
            st.rerun()

# 검색 로직
final_keyword = user_query
if btn_click: final_keyword = user_query
elif user_query: final_keyword = user_query

if final_keyword:
    if final_keyword not in history: history.insert(0, final_keyword)
    else: history.remove(final_keyword); history.insert(0, final_keyword)
    if len(history) > 20: history = history[:20]
    st.session_state['data']['history'] = history
    save_data(st.session_state['data'])

    with st.spinner("검색 중..."):
        data = get_naver_data(final_keyword)
        
        if data["meanings"]:
            c_title, c_star = st.columns([0.8, 0.2])
            with c_title:
                st.markdown(f"## :blue[{final_keyword}]")
            with c_star:
                is_fav = final_keyword in favorites
                icon = "⭐" if is_fav else "☆"
                # 별표 버튼 (type="secondary"로 CSS 적용)
                if st.button(icon, key="fav_toggle_btn", type="secondary"):
                    if is_fav: favorites.remove(final_keyword)
                    else: favorites.append(final_keyword)
                    save_data(st.session_state['data'])
                    st.rerun()

            aud = data["audio"]
            if aud["US"] or aud["GB"]:
                st.write("")
                ac1, ac2 = st.columns(2)
                with ac1:
                    if aud["US"]: st.caption("🇺🇸 미국"); st.audio(aud["US"], format='audio/mp3')
                with ac2:
                    if aud["GB"]: st.caption("🇬🇧 영국"); st.audio(aud["GB"], format='audio/mp3')

            st.write("") 
            for i, m in enumerate(data["meanings"], 1):
                st.markdown(f'<div class="result-box"><b>{i}.</b> {m}</div>', unsafe_allow_html=True)
        else:
             if user_query:
                st.warning("결과를 찾을 수 없습니다.")