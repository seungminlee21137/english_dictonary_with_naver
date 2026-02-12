import streamlit as st
import requests
import json
import re
import os

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
# 2. 크롤링 로직 (HTTPS 변환 추가)
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
                
                # [중요] HTTP를 HTTPS로 강제 변환 (보안 이슈 해결)
                if s_file and s_file.startswith("http://"):
                    s_file = s_file.replace("http://", "https://")

                if s_file:
                    if 'US' in s_type or '미국' in s_type:
                        result_dict["audio"]["US"] = s_file
                    elif 'GB' in s_type or '영국' in s_type:
                        result_dict["audio"]["GB"] = s_file
    except: pass
    return result_dict

# --------------------------------------------------------------------------
# 3. Streamlit 화면 구성
# --------------------------------------------------------------------------
st.set_page_config(page_title="나만의 AI 영한사전", page_icon="🎧", layout="wide")

st.markdown("""
<style>
    /* 전체 간격 조절 */
    [data-testid="stVerticalBlock"] { gap: 0.5rem !important; }

    /* 사이드바 스타일 */
    [data-testid="stSidebar"] div.stButton > button {
        text-align: left;
        width: auto;
        border: none;
        background-color: #f1f3f5;
        padding: 6px 10px;
        margin: 2px 0;
        border-radius: 6px;
        font-size: 14px;
        letter-spacing: -0.5px;
    }
    
    /* 최근 검색어 버튼 */
    .main div.stButton > button {
        border-radius: 20px;
        letter-spacing: -0.3px;
        padding: 4px 16px;
    }

    /* 결과 박스 */
    .result-box {
        background-color: #ffffff;
        padding: 14px 18px;
        border-radius: 8px;
        border-left: 5px solid #03c75a;
        margin-bottom: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

if 'data' not in st.session_state:
    st.session_state['data'] = load_data()
if 'search_input' not in st.session_state:
    st.session_state['search_input'] = ""

# --- 사이드바 ---
with st.sidebar:
    st.header("⭐ 단어장")
    favorites = st.session_state['data']['favorites']
    favorites.sort(key=str.lower)
    
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

# --- 메인 화면 ---
st.title("🎧 AI 영한사전")
keyword = st.text_input("단어를 입력하세요", key="search_widget", value=st.session_state['search_input'])

history = st.session_state['data']['history']
if history:
    h_col1, h_col2 = st.columns([0.85, 0.15])
    with h_col1: st.caption("🕒 최근 검색어")
    delete_mode = h_col2.toggle("🗑️ 삭제")
    
    cols = st.columns(6, gap="small")
    for i, h_word in enumerate(history):
        with cols[i % 6]:
            if delete_mode:
                if st.button(f"✕ {h_word}", key=f"del_{i}", type="primary"):
                    history.pop(i)
                    st.session_state['data']['history'] = history
                    save_data(st.session_state['data']); st.rerun()
            else:
                if st.button(h_word, key=f"hist_{i}"):
                    st.session_state['search_input'] = h_word; st.rerun()
    st.divider()

if keyword:
    if not delete_mode and keyword not in history:
        if keyword in history: history.remove(keyword)
        history.insert(0, keyword)
        st.session_state['data']['history'] = history[:20]
        save_data(st.session_state['data'])

    with st.spinner("검색 중..."):
        data = get_naver_data(keyword)
        
        if data["meanings"]:
            # 1. 단어 제목 + 즐겨찾기 버튼
            col1, col2 = st.columns([0.85, 0.15])
            col1.markdown(f"## :blue[{keyword}]")
            
            if keyword in favorites:
                if col2.button("⭐ 해제", type="primary"):
                    favorites.remove(keyword); save_data(st.session_state['data']); st.rerun()
            else:
                if col2.button("☆ 추가"):
                    favorites.append(keyword); save_data(st.session_state['data']); st.rerun()

            # 2. 오디오 플레이어 (st.audio 사용으로 깨짐 방지)
            aud = data["audio"]
            if aud["US"] or aud["GB"]:
                st.markdown("---") # 구분선
                
                # 오디오가 2개(미국/영국) 다 있으면 2단 컬럼, 하나면 1단
                ac1, ac2 = st.columns(2)
                
                with ac1:
                    if aud["US"]:
                        st.caption("🇺🇸 미국식 발음")
                        st.audio(aud["US"], format='audio/mp3')
                
                with ac2:
                    if aud["GB"]:
                        st.caption("🇬🇧 영국식 발음")
                        st.audio(aud["GB"], format='audio/mp3')

            st.markdown("---")

            # 3. 뜻 풀이
            for i, m in enumerate(data["meanings"], 1):
                st.markdown(f'<div class="result-box"><b>{i}.</b> {m}</div>', unsafe_allow_html=True)
        else:
            st.warning("결과를 찾을 수 없습니다.")