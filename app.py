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
# 2. 크롤링 로직 (HTTPS 변환 포함)
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
    # 모바일 API 엔드포인트가 차단이 덜 되는 경향이 있어 변경 시도
    # PC 버전: https://en.dict.naver.com/api3/enko/search?query=...
    url = f"https://en.dict.naver.com/api3/enko/search?query={keyword}&m=pc&lang=ko"
    
    headers = {
        # 크롬 브라우저인 척하는 강력한 헤더
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://en.dict.naver.com/",
        "Connection": "keep-alive"
    }
    
    result_dict = {"meanings": [], "audio": {"US": None, "GB": None}}
    
    try:
        response = requests.get(url, headers=headers, timeout=5) # 5초 타임아웃 설정
        
        # [디버깅] 상태 코드가 200(성공)이 아니면 에러 메시지를 화면에 출력
        if response.status_code != 200:
            st.error(f"서버 연결 오류: {response.status_code}")
            # 403이면 차단됨, 500이면 네이버 서버 오류
            return result_dict

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
                
                if s_file and s_file.startswith("http://"):
                    s_file = s_file.replace("http://", "https://")

                if s_file:
                    if 'US' in s_type or '미국' in s_type:
                        result_dict["audio"]["US"] = s_file
                    elif 'GB' in s_type or '영국' in s_type:
                        result_dict["audio"]["GB"] = s_file
    except Exception as e:
        # 에러 발생 시 로그 출력
        st.error(f"에러 발생: {str(e)}")
        pass
        
    return result_dict

# --------------------------------------------------------------------------
# 3. Streamlit 화면 구성 (모바일 최적화)
# --------------------------------------------------------------------------
st.set_page_config(page_title="나만의 AI 영한사전", page_icon="🎧", layout="wide")

st.markdown("""
<style>
    /* =========================================
       [모바일 최적화 - Galaxy S25 Ultra 기준]
       ========================================= */
    
    /* 1. 기본 폰트 및 간격 조정 */
    html, body, [class*="css"] {
        font-family: 'Pretendard', sans-serif;
    }
    [data-testid="stVerticalBlock"] { gap: 0.6rem !important; }

    /* 2. 사이드바 (단어장) 스타일 */
    [data-testid="stSidebar"] div.stButton > button {
        text-align: left;
        width: 100%; /* 모바일에서는 꽉 차게 */
        border: none;
        background-color: #f8f9fa;
        padding: 12px 10px; /* 터치 영역 확대 */
        margin: 2px 0;
        border-radius: 8px;
        font-size: 15px; /* 글씨 키움 */
        font-weight: 500;
        letter-spacing: -0.3px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    [data-testid="stSidebar"] div.stButton > button:hover {
        background-color: #e9ecef;
        color: #03c75a;
    }

    /* 3. 최근 검색어 버튼 (알약 모양) - 크고 누르기 쉽게 */
    .main div.stButton > button {
        width: 100%;
        border-radius: 12px; /* 둥근 사각형 */
        letter-spacing: -0.5px;
        padding: 8px 4px; /* 높이 확보 */
        min-height: 45px; /* 최소 높이 지정 (터치 미스 방지) */
        font-size: 15px;
        font-weight: 500;
        border: 1px solid #e0e0e0;
        background-color: white;
        white-space: nowrap; /* 줄바꿈 방지 */
        overflow: hidden;
        text-overflow: ellipsis; /* 긴 단어는 ... 처리 */
    }
    .main div.stButton > button:active, .main div.stButton > button:focus {
        border-color: #03c75a;
        color: #03c75a;
        background-color: #e8f5e9;
    }

    /* 4. 결과 박스 (뜻 풀이) */
    .result-box {
        background-color: #ffffff;
        padding: 16px 20px;
        border-radius: 12px;
        border-left: 6px solid #03c75a;
        margin-bottom: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.08);
        font-size: 16px;
        line-height: 1.5;
    }

    /* 5. 모바일 전용 미디어 쿼리 (가로폭 768px 이하) */
    @media (max-width: 768px) {
        /* 사이드바 삭제 버튼 정렬 보정 */
        [data-testid="stSidebar"] div[data-testid="column"] {
             min-width: 0 !important;
        }
        
        /* 메인화면 여백 줄이기 */
        .block-container {
            padding-top: 2rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }
        
        /* 텍스트 인풋(검색창) 키우기 */
        .stTextInput > div > div > input {
            font-size: 16px;
            padding: 10px;
            height: 50px; /* 입력창 높이 확대 */
        }
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
            # 비율 조정 (단어 8 : 삭제 2)
            c1, c2 = st.columns([0.8, 0.2], gap="small")
            with c1:
                if st.button(f"📄 {fav_word}", key=f"fav_{fav_word}"):
                    st.session_state['search_input'] = fav_word
                    st.rerun()
            with c2:
                # 삭제 버튼 빨간색 강조
                if st.button("✕", key=f"fav_del_{fav_word}", type="primary"):
                    favorites.remove(fav_word)
                    st.session_state['data']['favorites'] = favorites
                    save_data(st.session_state['data'])
                    st.rerun()

# --- 메인 화면 ---
st.title("🎧 AI 영한사전")

# 검색창에 placeholder 추가하여 가이드 제공
keyword = st.text_input("단어를 입력하세요", key="search_widget", value=st.session_state['search_input'], placeholder="예: apple, love")

history = st.session_state['data']['history']

# [최근 검색어 영역]
if history:
    st.markdown("---")
    h_col1, h_col2 = st.columns([0.7, 0.3])
    with h_col1: st.caption(f"🕒 최근 검색 ({len(history)}개)")
    with h_col2: delete_mode = st.toggle("삭제모드")
    
    # [모바일 최적화] S25 Ultra 화면 폭에 맞춰 6열 -> 3열로 변경
    # 3열이 모바일에서 버튼 크기가 적당히 크고 예쁨
    cols = st.columns(3, gap="small") 
    
    for i, h_word in enumerate(history):
        with cols[i % 3]: # 3으로 나눈 나머지로 인덱스 배정
            if delete_mode:
                if st.button(f"✕ {h_word}", key=f"del_{i}", type="primary"):
                    history.pop(i)
                    st.session_state['data']['history'] = history
                    save_data(st.session_state['data']); st.rerun()
            else:
                if st.button(h_word, key=f"hist_{i}"):
                    st.session_state['search_input'] = h_word; st.rerun()
    st.markdown("---")


if keyword:
    if not delete_mode and keyword not in history:
        if keyword in history: history.remove(keyword)
        history.insert(0, keyword)
        st.session_state['data']['history'] = history[:20]
        save_data(st.session_state['data'])

    with st.spinner("검색 중..."):
        data = get_naver_data(keyword)
        
        if data["meanings"]:
            # 1. 단어 제목 + 즐겨찾기 (모바일 레이아웃 조정)
            c_title, c_fav = st.columns([0.75, 0.25])
            with c_title:
                st.markdown(f"## :blue[{keyword}]")
            with c_fav:
                if keyword in favorites:
                    if st.button("⭐ On", type="primary", use_container_width=True):
                        favorites.remove(keyword); save_data(st.session_state['data']); st.rerun()
                else:
                    if st.button("☆ Off", use_container_width=True):
                        favorites.append(keyword); save_data(st.session_state['data']); st.rerun()

            # 2. 오디오 플레이어
            aud = data["audio"]
            if aud["US"] or aud["GB"]:
                st.write("") # 약간의 여백
                # 모바일에서는 버튼이 작아보일 수 있으므로 오디오도 100% 폭 활용
                ac1, ac2 = st.columns(2)
                with ac1:
                    if aud["US"]:
                        st.caption("🇺🇸 미국")
                        st.audio(aud["US"], format='audio/mp3')
                with ac2:
                    if aud["GB"]:
                        st.caption("🇬🇧 영국")
                        st.audio(aud["GB"], format='audio/mp3')

            st.write("") # 여백

            # 3. 뜻 풀이 (깔끔한 카드 스타일)
            for i, m in enumerate(data["meanings"], 1):
                st.markdown(f'<div class="result-box"><b>{i}.</b> {m}</div>', unsafe_allow_html=True)
        else:
            st.warning("결과를 찾을 수 없습니다.")