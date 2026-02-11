import requests
import json
import re

def clean_html(raw_html):
    """<strong> 등의 HTML 태그를 제거합니다."""
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html)

def extract_values_deeply(data):
    """딕셔너리, 리스트, 그리고 문자열 속에 숨은 JSON까지 모두 뒤져 'value'를 찾습니다."""
    results = []
    
    if isinstance(data, dict):
        for k, v in data.items():
            # 1. 'value' 키를 찾은 경우
            if k == 'value' and isinstance(v, str) and v.strip():
                results.append(clean_html(v))
            
            # 2. 문자열인데 그 안에 JSON이 숨어있는 경우 (expOnly 등)
            elif isinstance(v, str) and v.startswith('{') and ('"value"' in v or '"means"' in v):
                try:
                    inner_json = json.loads(v)
                    results.extend(extract_values_deeply(inner_json))
                except:
                    pass
            
            # 3. 나머지는 재귀적으로 탐색
            else:
                results.extend(extract_values_deeply(v))
                
    elif isinstance(data, list):
        for item in data:
            results.extend(extract_values_deeply(item))
            
    return results

def get_naver_dict(keyword):
    # API 주소 (hid 값은 생략해도 무방하나, 봇 차단 회피를 위해 헤더가 중요함)
    url = f"https://en.dict.naver.com/api3/enko/search?query={keyword}&m=pc&lang=ko"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Referer": "https://en.dict.naver.com/",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://en.dict.naver.com"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # 전체 응답 데이터
        full_data = response.json()

        # [디버깅] 데이터가 어디에 숨어있든 다 찾기 위해 전체 데이터를 대상으로 탐색
        # searchResultListMap 뿐만 아니라 전체 응답(full_data)을 다 뒤집니다.
        all_found_values = extract_values_deeply(full_data)

        # 한글이 포함된 "뜻"만 골라내기
        meaning_results = []
        for val in dict.fromkeys(all_found_values): # 중복 제거
            # 한글 포함 여부 확인 및 단순 검색어(apple)와 일치하는 결과 제외
            if any(ord('가') <= ord(char) <= ord('힣') for char in val):
                if val != keyword:
                    meaning_results.append(val)

        if not meaning_results:
            print(f"🔍 '{keyword}'에 대한 유효한 검색 결과가 없습니다.")
            # 만약 결과가 없다면 데이터 구조가 아예 비어있는지 확인용
            if not full_data.get("searchResultListMap") and not full_data.get("searchResultMap"):
                 print("⚠️ 네이버 서버에서 데이터를 보내주지 않았습니다. (요청 차단 가능성)")
            return

        print(f"\n✅ '{keyword}' 뜻 풀이 결과:")
        print("-" * 30)
        for i, val in enumerate(meaning_results[:10], 1): # 상위 10개만
            print(f"{i}. {val}")
        print("-" * 30)

    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    word = input("검색할 영단어를 입력하세요: ").strip()
    if word:
        get_naver_dict(word)