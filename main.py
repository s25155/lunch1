import calendar
from datetime import datetime
import re
import requests
import streamlit as st

# ==========================================
# 1. 페이지 설정 및 커스텀 CSS (스타일링)
# ==========================================
st.set_page_config(
    page_title="한 달치 학교 급식 달력 🍱", page_icon="🍱", layout="wide"
)

# 하이라이트 및 배지 스타일
st.markdown(
    """
    <style>
    .stApp {
        background-color: #f8f9fa;
    }
    
    /* 급식 종류 및 칼로리 표시 */
    .badge-lunch { color: #1e88e5; font-weight: bold; font-size: 0.92rem; margin-bottom: 4px; }
    .badge-dinner { color: #e53935; font-weight: bold; font-size: 0.92rem; margin-bottom: 4px; }
    .badge-other { color: #43a047; font-weight: bold; font-size: 0.92rem; margin-bottom: 4px; }
    .calorie-text { font-size: 0.78rem; color: #718096; font-weight: normal; }

    /* 메뉴 항목 스타일 */
    .menu-item {
        font-size: 0.85rem;
        color: #2d3748;
        line-height: 1.5;
        margin: 3px 0;
    }
    
    /* ⭐ 맛있는 메뉴 형광펜 하이라이트 */
    .highlight-yummy {
        background: linear-gradient(120deg, #fff176 0%, #ffd54f 100%);
        color: #1a202c;
        font-weight: bold;
        padding: 2px 5px;
        border-radius: 4px;
        display: inline-block;
    }
    
    /* 알레르기 안내 텍스트 */
    .allergy-info {
        font-size: 0.75rem;
        color: #a0aec0;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# ==========================================
# 2. 알레르기 및 인기 메뉴 키워드 정의
# ==========================================
ALLERGY_MAP = {
    "1": "난류",
    "2": "우유",
    "3": "메밀",
    "4": "땅콩",
    "5": "대두",
    "6": "밀",
    "7": "고등어",
    "8": "게",
    "9": "새우",
    "10": "돼지고기",
    "11": "복숭아",
    "12": "토마토",
    "13": "아황산류",
    "14": "호두",
    "15": "닭고기",
    "16": "쇠고기",
    "17": "오징어",
    "18": "조개류",
    "19": "잣",
}

SPECIAL_KEYWORDS = [
    "치킨",
    "닭",
    "고기",
    "불고기",
    "갈비",
    "돈까스",
    "돈가스",
    "가츠",
    "카츠",
    "스테이크",
    "떡볶이",
    "파스타",
    "스파게티",
    "피자",
    "햄버거",
    "소시지",
    "소세지",
    "핫도그",
    "와플",
    "아이스크림",
    "푸딩",
    "케이크",
    "에이드",
    "주스",
    "쥬스",
    "식혜",
    "타코야끼",
    "초밥",
    "그라탕",
    "젤리",
    "요거트",
]


# ==========================================
# 3. 헬퍼 함수
# ==========================================
def format_menu_items(menu_str, convert_allergy=False):
    """메뉴 문자열을 파싱하여 알레르기 변환 및 형광펜/별표 적용"""
    if not menu_str:
        return ""

    lines = str(menu_str).split("<br/>")
    formatted_html_list = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 특수 기호(&, && 등) 정리
        clean_line = re.sub(r"^&+", "", line).strip()

        # 1. 알레르기 숫자 변환
        if convert_allergy:

            def replace_allergy(match):
                numbers = match.group(1).split(".")
                names = [ALLERGY_MAP.get(num, num) for num in numbers if num]
                return (
                    f" <span class='allergy-info'>({', '.join(names)})</span>"
                )

            clean_line = re.sub(r"\(([\d\.]+)\)", replace_allergy, clean_line)

        # 2. 맛있는 메뉴 키워드 검사
        is_special = any(keyword in clean_line for keyword in SPECIAL_KEYWORDS)

        if is_special:
            item_html = f"<div class='menu-item'>⭐ <span class='highlight-yummy'>{clean_line}</span></div>"
        else:
            item_html = f"<div class='menu-item'>• {clean_line}</div>"

        formatted_html_list.append(item_html)

    return "".join(formatted_html_list)


@st.cache_data(ttl=3600)
def fetch_month_meals(office_code, school_code, year, month, api_key):
    """NEIS API에서 지정된 월의 전체 급식 데이터 조회"""
    _, last_day = calendar.monthrange(year, month)

    from_ymd = f"{year}{month:02d}01"
    to_ymd = f"{year}{month:02d}{last_day:02d}"

    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    params = {
        "KEY": api_key,
        "Type": "json",
        "pIndex": 1,
        "pSize": 100,
        "ATPT_OFCDC_SC_CODE": office_code,
        "SD_SCHUL_CODE": school_code,
        "MLSV_FROM_YMD": from_ymd,
        "MLSV_TO_YMD": to_ymd,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "mealServiceDietInfo" in data:
            return data["mealServiceDietInfo"][1]["row"], None
        elif "RESULT" in data:
            if data["RESULT"]["CODE"] == "INFO-200":
                return [], None
            return None, f"API 오류: {data['RESULT']['MESSAGE']}"
        else:
            return None, "알 수 없는 응답 형식입니다."

    except requests.exceptions.Timeout:
        return None, "API 서버 응답 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요."
    except requests.exceptions.RequestException as e:
        return None, f"API 통신 실패: {e}"


# ==========================================
# 4. 사이드바 및 설정
# ==========================================
st.sidebar.title("⚙️ 설정 및 안내")

# API 키 확인
if "NEIS_KEY" not in st.secrets:
    st.error(
        "⚠️ `.streamlit/secrets.toml` 파일에 `NEIS_KEY`가 설정되어 있는지 확인해 주세요."
    )
    st.stop()

api_key = st.secrets["NEIS_KEY"]

# T10 (제주특별자치도교육청) 기본값 설정
office_code = st.sidebar.text_input("시도교육청코드", value="T10")
school_code = st.sidebar.text_input("표준학교코드", value="9290088")

st.sidebar.markdown("---")

convert_allergy = st.sidebar.toggle(
    "알레르기 식품명으로 변환",
    value=False,
    help="메뉴 옆의 숫자를 실제 식재료 이름으로 바꿉니다.",
)

with st.sidebar.expander("ℹ️ 알레르기 번호 안내표"):
    for code, name in ALLERGY_MAP.items():
        st.write(f"**{code}번**: {name}")

st.sidebar.markdown("---")
st.sidebar.caption("💡 **팁**: 인기 메뉴는 자동으로 ⭐형광펜 표시됩니다!")


# ==========================================
# 5. 상단 컨트롤 및 메인 화면
# ==========================================
st.title("🍱 한 달치 학교 급식 달력")

now = datetime.now()
col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    selected_year = st.selectbox(
        "연도 선택", range(now.year - 1, now.year + 2), index=1
    )

with col2:
    selected_month = st.selectbox("월 선택", range(1, 13), index=now.month - 1)

with col3:
    meal_filter = st.radio(
        "급식 종류 필터",
        ["전체 보기", "중식만 보기", "석식만 보기"],
        horizontal=True,
    )

st.markdown("---")


# ==========================================
# 6. API 데이터 불러오기 및 정제
# ==========================================
meal_raw_data, error_msg = fetch_month_meals(
    office_code, school_code, selected_year, selected_month, api_key
)

if error_msg:
    st.error(f"🚨 {error_msg}")
    st.stop()

# 날짜별, 급식종류별 데이터 정리
monthly_meals = {}
if meal_raw_data:
    for row in meal_raw_data:
        try:
            day = int(row["MLSV_YMD"][6:8])
            meal_name = str(row["MMEAL_SC_NM"]).strip()  # 중식, 석식 등
            menu_text = row["DDISH_NM"]

            # 칼로리 정보 정제
            cal_raw = str(row.get("CAL_INFO", ""))
            cal_match = re.search(r"([\d\.]+\s*Kcal)", cal_raw)
            cal_str = cal_match.group(1) if cal_match else cal_raw

            if day not in monthly_meals:
                monthly_meals[day] = {}

            monthly_meals[day][meal_name] = {
                "menu": menu_text,
                "cal": cal_str,
            }
        except Exception as e:
            st.error(f"데이터 파싱 중 오류: {e}")


# ==========================================
# 7. 달력 화면 렌더링 (안전한 레이아웃)
# ==========================================
try:
    month_cal = calendar.monthcalendar(selected_year, selected_month)
    days_of_week = ["월요일", "화요일", "수요일", "목요일", "금요일"]

    for week_idx, week in enumerate(month_cal):
        workdays = week[:5]  # 월~금 평일만 추출

        if sum(workdays) == 0:
            continue

        st.markdown(f"#### 🗓️ {week_idx + 1}주차")
        cols = st.columns(5)

        for i, day in enumerate(workdays):
            with cols[i]:
                # 지난 달 / 다음 달 날짜 처리
                if day == 0:
                    st.caption(f"{days_of_week[i]}")
                    st.info("다른 달")
                    continue

                is_today = (
                    selected_year == now.year
                    and selected_month == now.month
                    and day == now.day
                )

                # 테두리 컨테이너 사용으로 UI 깨짐 완전 방지
                with st.container():
                    today_badge = " 🔥 **TODAY**" if is_today else ""
                    st.markdown(
                        f"**{day}일 ({days_of_week[i][0]})**{today_badge}"
                    )

                    if day not in monthly_meals:
                        st.caption("😴 급식 없음")
                    else:
                        day_meals = monthly_meals[day]
                        displayed_any = False

                        # 중식 -> 석식 순서 정렬
                        sorted_meals = sorted(
                            day_meals.items(),
                            key=lambda x: 0 if x[0] == "중식" else 1,
                        )

                        for meal_type, meal_info in sorted_meals:
                            if (
                                meal_filter == "중식만 보기"
                                and meal_type != "중식"
                            ):
                                continue
                            if (
                                meal_filter == "석식만 보기"
                                and meal_type != "석식"
                            ):
                                continue

                            displayed_any = True

                            cal_str = (
                                f" <span class='calorie-text'>({meal_info['cal']})</span>"
                                if meal_info["cal"]
                                else ""
                            )

                            if meal_type == "중식":
                                st.markdown(
                                    f"<div class='badge-lunch'>🔵 {meal_type}{cal_str}</div>",
                                    unsafe_allow_html=True,
                                )
                            else:
                                st.markdown(
                                    f"<div class='badge-dinner'>🔴 {meal_type}{cal_str}</div>",
                                    unsafe_allow_html=True,
                                )

                            formatted_menu = format_menu_items(
                                meal_info["menu"], convert_allergy
                            )
                            st.markdown(formatted_menu, unsafe_allow_html=True)

                        if not displayed_any:
                            st.caption("🔍 해당 식단 없음")

except Exception as e:
    st.error(f"🖥️ 화면을 구성하는 중에 오류가 발생했습니다: {e}")
