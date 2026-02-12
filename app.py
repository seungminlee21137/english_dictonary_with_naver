import streamlit as st
import requests
import json
import re
import os
import uuid

# --------------------------------------------------------------------------
# 1. 데이터 관리 (저장/로드)
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
# 2. 오디오 버튼 디자인 (HTML/JS)
# --------------------------------------------------------------------------
def style_audio_button(url, label, icon):
    unique_id = str(uuid.uuid4())
    button_style = """
        background-color: #f0f2f6;
        border: 1px solid #dce4ef;
        border-radius: 20px;
        color: #31333F;
        padding: 6px 16px;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 15px;
        font-weight: 600;
        margin: 0 5px;
        cursor: pointer;
        transition-duration: 0.2s;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    """
    hover_script = f"""
        onmouseover="this.style.backgroundColor='#e0e2e6'; this.style.borderColor='#c8d0db';"
        onmouseout="this.style.backgroundColor='#f0f2f6'; this.style.borderColor='#dce4ef';"
    """
    html_code = f"""
        <div style="display:inline-block;">
            <audio id="audio_{unique_id}" src="{url}"></audio>
            <button style="{button_style}" onclick="document.getElementById('audio_{unique_id}').play()" {hover_script}>
                {icon} {label}
            </button>
        </div>
    """
    return html_code

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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Referer": "https://en.dict.naver.com/",
    }
    
    result_dict = {"meanings": [], "audio": {"US": None, "GB": None}}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200: return result_dict
        full_data = response.json()
        
        all_found_values = extract_values_deeply(full_data)
        meaning_results = []
        for val in dict.fromkeys(all_found_values):
            if any(ord('가') <= ord(char) <= ord('힣') for char in val):
                if val != keyword:
                    meaning_results.append(val)
        result_dict["meanings"] = meaning_results[:15]

        audio_list = extract_audio_deeply(full_data)
        if audio_list:
            for item in audio_list:
                s_type = str(item.get('symbolType', '')).upper()
                s_file = item.get('symbolFile', '')
                if not s_type and 'US' in str(item): s_type = 'US'
                if not s_type and 'GB' in str(item): s_type = 'GB'
                if s_file:
                    if 'US' in s_type or '미국' in s_type:
                        result_dict["audio"]["US"] = s_file
                    elif 'GB' in s_type or '영국' in s_type:
                        result_dict["audio"]["GB"] = s_file
    except: pass
    return result_dict

# --------------------------------------------------------------------------
# 4. Streamlit 화면 구성
# --------------------------------------------------------------------------
st.set_page_config(page_title="나만의 AI 영한사전", page_icon="🎧", layout="wide")

st.markdown("""
<style>
    /* 1. 사이드바 (즐겨찾기) 스타일 - width 100% 제거 */
    [data-testid="stSidebar"] div.stButton > button {
        text-align: left;           /* 왼쪽 정렬 */
        width: auto;                /* 내용만큼만 너비 차지 */
        border: none;               /* 테두리 없애기 */
        background-color: transparent; 
        padding-left: 5px;          
    }
    [data-testid="stSidebar"] div.stButton > button:hover {
        background-color: #f0f2f6;  
        color: #03c75a;             
        font-weight: bold;
    }
    
    /* 사이드바 삭제 버튼 정렬 */
    [data-testid="stSidebar"] div[data-testid="column"] + div[data-testid="column"] div.stButton > button {
        text-align: center;
        width: 100%; /* 삭제 버튼은 클릭 편의상 넓게 */
        color: #999;
    }

    /* 2. 메인 화면 알약 버튼 */
    .main div.stButton > button {
        border-radius: 20px;
        border: 1px solid #e0e0e0;
        background-color: white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        transition: all 0.2s ease-in-out;
        font-size: 14px;
        color: #333;
    }
    .main div.stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        border-color: #03c75a;
        color: #03c75a;
    }
    .main div.stButton > button[kind="primary"] {
        background-color: #ff4b4b !important;
        color: white !important;
        border: none !important;
    }

    /* 3. 결과 박스 */
    .result-box {
        background-color: #f9f9f9;
        padding: 18px;
        border-radius: 12px;
        border-left: 6px solid #03c75a;
        margin-bottom: 12px;
        font-size: 16px;
        line-height: 1.6;
    }
</style>
""", unsafe_allow_html=True)

if 'data' not in st.session_state:
    st.session_state['data'] = load_data()
if 'search_input' not in st.session_state:
    st.session_state['search_input'] = ""

# --- 사이드바: 즐겨찾기 ---
with st.sidebar:
    st.header("⭐ 단어장")
    st.markdown("---")
    
    favorites = st.session_state['data']['favorites']
    favorites.sort(key=str.lower) # ABC 순 정렬
    
    if favorites:
        for fav_word in favorites:
            c1, c2 = st.columns([0.8, 0.2])
            with c1:
                if st.button(f"📄 {fav_word}", key=f"fav_{fav_word}"):
                    st.session_state['search_input'] = fav_word
                    st.rerun()
            with c2:
                if st.button("✕", key=f"fav_del_{fav_word}"):
                    favorites.remove(fav_word)
                    st.session_state['data']['favorites'] = favorites
                    save_data(st.session_state['data'])
                    st.rerun()
    else:
        st.info("단어를 추가해보세요!")

# --- 메인 화면 ---
st.title("🎧 듣는 AI 영한사전")

keyword = st.text_input("단어 검색", key="search_widget", value=st.session_state['search_input'])

delete_mode = False
history = st.session_state['data']['history']

if history:
    h_col1, h_col2 = st.columns([0.85, 0.15])
    with h_col1:
        st.caption("🕒 최근 검색어")
    with h_col2:
        delete_mode = st.toggle("🗑️ 삭제", key="del_mode")

    if delete_mode:
        if st.button("🚨 전체 삭제", type="primary", use_container_width=True):
            st.session_state['data']['history'] = []
            save_data(st.session_state['data'])
            st.rerun()

    cols = st.columns(6, gap="small")
    for i, h_word in enumerate(history):
        with cols[i % 6]:
            if delete_mode:
                if st.button(f"✕ {h_word}", key=f"del_btn_{i}", type="primary", use_container_width=True):
                    history.pop(i)
                    st.session_state['data']['history'] = history
                    save_data(st.session_state['data'])
                    st.rerun()
            else:
                if st.button(h_word, key=f"hist_{i}", use_container_width=True):
                    st.session_state['search_input'] = h_word
                    st.rerun()
    st.divider()

if keyword:
    if not delete_mode:
        if keyword in history: history.remove(keyword)
        history.insert(0, keyword)
        if len(history) > 20: history = history[:20]
        st.session_state['data']['history'] = history
        save_data(st.session_state['data'])

    with st.spinner(f"'{keyword}' 분석 중..."):
        data = get_naver_data(keyword)
        meanings = data["meanings"]
        audios = data["audio"]

        if meanings:
            col1, col2 = st.columns([0.85, 0.15])
            with col1:
                st.markdown(f"## :blue[{keyword}]")
            with col2:
                if keyword in st.session_state['data']['favorites']:
                    if st.button("⭐ 해제", type="primary", use_container_width=True):
                        st.session_state['data']['favorites'].remove(keyword)
                        save_data(st.session_state['data'])
                        st.rerun()
                else:
                    if st.button("☆ 추가", use_container_width=True):
                        if keyword not in st.session_state['data']['favorites']:
                            st.session_state['data']['favorites'].append(keyword)
                            save_data(st.session_state['data'])
                            st.rerun()

            audio_html_list = []
            if audios["US"]:
                audio_html_list.append(style_audio_button(audios["US"], "듣기", "🔊 🇺🇸"))
            if audios["GB"]:
                audio_html_list.append(style_audio_button(audios["GB"], "듣기", "🔊 🇬🇧"))
            
            if audio_html_list:
                combined_html = "&nbsp;&nbsp;".join(audio_html_list)
                st.markdown(f"<div style='margin-bottom: 20px;'>{combined_html}</div>", unsafe_allow_html=True)
            
            st.markdown("---")

            for i, val in enumerate(meanings, 1):
                st.markdown(
                    f"""
                    <div class="result-box">
                        <span style="font-weight:bold; font-size:1.2em; color:#03c75a; margin-right:12px;">{i}.</span>
                        <span style="font-size:1.1em; color:#333;">{val}</span>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
        else:
            st.warning("검색 결과가 없습니다.")

st.markdown("<br><br>", unsafe_allow_html=True)
st.caption("Data provided by Naver Dictionary API")