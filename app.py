import streamlit as st
import requests
import json
import re

# --- 로직 함수 (기존과 동일) ---
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

# --- 웹 화면 구성 (Streamlit) ---
st.set_page_config(page_title="나만의 AI 영한사전", page_icon="📖")

st.title("📖 나만의 AI 영한사전")
st.write("네이버 사전 데이터를 활용한 웹 사전입니다.")

# 검색창
keyword = st.text_input("검색할 영단어를 입력하고 엔터를 누르세요", placeholder="예: apple, query, alert")

if keyword:
    url = f"https://en.dict.naver.com/api3/enko/search?query={keyword}&m=pc&lang=ko"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Referer": "https://en.dict.naver.com/",
    }

    with st.spinner('사전에서 찾는 중...'):
        try:
            response = requests.get(url, headers=headers)
            full_data = response.json()
            all_found_values = extract_values_deeply(full_data)

            # 한글 뜻만 필터링
            meaning_results = []
            for val in dict.fromkeys(all_found_values):
                if any(ord('가') <= ord(char) <= ord('힣') for char in val):
                    if val != keyword:
                        meaning_results.append(val)

            if meaning_results:
                st.success(f"'{keyword}'의 검색 결과입니다.")
                for i, val in enumerate(meaning_results[:15], 1):
                    st.write(f"**{i}.** {val}")
            else:
                st.warning("검색 결과가 없습니다.")
                
        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")

# 하단 정보
st.divider()
st.caption("Data provided by Naver Dictionary API")