import calendar
from datetime import datetime
import re
import requests
import streamlit as st

# ==========================================
# 1. 페이지 설정 및 커스텀 CSS (형광펜 & 카드 스타일)
# ==========================================
st.set_page_config(
    page_title="한 달치 학교 급식 달력 🍱", page_icon="🍱", layout="wide"
)

# 카드 및 형광펜 효과를 위한 CSS 스타일링
st.markdown(
    """
    <style>
    /* 메인 배경 */
    .stApp {
        background-color: #f8f9fa;
    }
    /* 달력 카드 기본 스타일 */
    .meal-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.03);
        min-height: 190px;
    }
    /* 오늘 날짜 카드 강조 */
    .meal-card-today {
        border: 2px solid #ff4b4b !important;
        background-color: #fff8f8 !important;
    }
    /* 날짜 헤더 */
    .date-header {
        font-size: 1rem;
        font-weight: bold;
        color: #2d3748;
        margin-bottom: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    /* TODAY 태그 */
    .today-tag {
        background-color: #ff4b4b;
        color: white;
        font-size: 0.7rem;
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: bold;
    }
    /* 급식 종류 및 칼로리 헤더 */
    .badge-lunch { color: #1e88e5; font-weight: bold; font-size: 0.88rem; margin-top: 6px; }
    .badge-dinner { color: #e53935; font-weight: bold; font-size: 0.88rem; margin-top: 6px; }
    .badge-other { color: #43a047; font-weight: bold; font-size: 0.88rem; margin-top: 6px; }
    .calorie-text { font-size: 0.78rem; color: #718096; font-weight: normal; }

    /* 메뉴 아이템 스타일 */
    .menu-item {
        font-size: 0.85rem;
        color: #4a5568;
        line-height: 1.4;
        margin: 2px 0;
    }
    /* ⭐ 맛있는 메뉴 형광펜 하이라이트 */
    .highlight-yummy {
        background: linear-gradient(120deg, #fff176 0%, #ffd54f 100%);
        color: #1a202c;
        font-weight: bold;
        padding: 1px 4px;
        border-radius: 3px;
    }
    /* 급식 없음/해당 없음 텍스트 */
    .no-meal {
        color: #a0aec0;
        font-size: 0.82rem;
        font-style: italic;
        margin-top: 8px;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# ==========================================
# 2. 알레르기 및 맛있는 메뉴 키워드 정의
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

# ⭐ 형광펜 칠하고 별표 표시할 인기/맛있는 메뉴 키워드 목록
SPECIAL_KEYWORDS = [
    "치킨",
    "닭강정",
    "고기",
    "불고기",
    "갈비",
    "삼겹",
    "돈가스",
    "돈까스",
    "카츠",
    "스테이크",
    "떡볶이",
    "스파게티",
    "파스타",
    "피자",
    "햄버거",
    "짜장",
    "짬뽕",
    "탕수육",
    "우동",
    "라멘",
    "마라",
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
]


# ==========================================
# 3. 헬퍼 함수
# ==========================================
def format_menu_items(menu_str, convert_allergy=False):
    """메뉴 문자열을 파싱하여 알레르기 변환 및 형광펜/별표 하이라이트를 적용한 HTML을 반환합니다."""
    lines = menu_str.split("<br/>")
    formatted_html = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 1. 알레르기 숫자 변환 처리
        if convert_allergy:

            def replace_allergy(match):
                numbers = match.group(1).split(".")
                names = [ALLERGY_MAP.get(num, num) for num in numbers if num]
                return f" <span style='font-size:0.75rem; color:#a0aec0;'>({', '.join(names)})</span>"

            line = re.sub(r"\(([\d\.]+)\)", replace_allergy, line)

        # 2. 맛있는 메뉴 키워드 포함 여부 검사
        is_special = any(keyword in line for keyword in SPECIAL_KEYWORDS)

        if is_special:
            item_code = f"<div class='menu-item'>⭐ <span class='highlight-yummy'>{line}</span></div>"
        else:
            item_code = f"<div class='menu-item'>• {line}</div>"

        formatted_html.append(item_code)

    return "".join(formatted_html)


@st.cache_data(ttl=3600)
def fetch_month_meals(office_code, school_code, year, month, api_key):
    """NEIS API에서 지정된 월의 전체 급식 데이터를 조회합니다."""
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
# 4. 사이드바 구성
# ==========================================
st.sidebar.title("⚙️ 설정 및 안내")

# API 키 확인
if "NEIS_KEY" not in st.secrets:
    st.error(
        "⚠️ `secrets.toml`에 `NEIS_KEY`가 설정되지 않았습니다.\n.streamlit/secrets.toml 파일에 키를 추가해 주세요."
    )
    st.stop()

api_key = st.secrets["NEIS_KEY"]

# 학교 정보 입력창
office_code = st.sidebar.text_input("시도교육청코드", value="B10")
school_code = st.sidebar.text_input("표준학교코드", value="7010537")

st.sidebar.markdown("---")

# 알레르기 변환 옵션
convert_allergy = st.sidebar.toggle(
    "알레르기 식품명으로 변환",
    value=False,
    help="메뉴 옆의 숫자를 실제 식재료 이름으로 바꿉니다.",
)

# 알레르기 안내표
with st.sidebar.expander("ℹ️ 알레르기 번호 안내표"):
    for code, name in ALLERGY_MAP.items():
        st.write(f"**{code}번**: {name}")

st.sidebar.markdown("---")
st.sidebar.caption("💡 **팁**: 인기 메뉴(치킨, 고기, 떡볶이 등)는 자동으로 ⭐형광펜 표시됩니다!")


# ==========================================
# 5. 상단 필터 및 메인 화면
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
# 6. 데이터 불러오기 및 처리
# ==========================================
meal_raw_data, error_msg = fetch_month_meals(
    office_code, school_code, selected_year, selected_month, api_key
)

if error_msg:
    st.error(f"🚨 {error_msg}")
    st.stop()

# 날짜별, 급식종류별 데이터 매핑 구조: {일(int): {급식명: {'menu': ..., 'cal': ...}}}
monthly_meals = {}
if meal_raw_data:
    for row in meal_raw_data:
        try:
            day = int(row["MLSV_YMD"][6:8])
            meal_name = row["MMEAL_SC_NM"]  # 조식, 중식, 석식 등
            menu_text = row["DDISH_NM"]
            calorie_info = row.get("CAL_INFO", "")  # 칼로리 정보 추출

            if day not in monthly_meals:
                monthly_meals[day] = {}

            monthly_meals[day][meal_name] = {
                "menu": menu_text,
                "cal": calorie_info,
            }
        except Exception as e:
            st.error(f"데이터 파싱 실패: {e}")


# ==========================================
# 7. 달력 화면 렌더링
# ==========================================
try:
    month_cal = calendar.monthcalendar(selected_year, selected_month)
    days_of_week = ["월요일", "화요일", "수요일", "목요일", "금요일"]

    for week_idx, week in enumerate(month_cal):
        workdays = week[:5]  # 월~금 평일만 사용

        if sum(workdays) == 0:
            continue

        st.subheader(f"🗓️ {week_idx + 1}주차")
        cols = st.columns(5)

        for i, day in enumerate(workdays):
            with cols[i]:
                # 지난 달 / 다음 달 날짜 처리
                if day == 0:
                    st.markdown(
                        """
                        <div class="meal-card" style="opacity: 0.4;">
                            <div class="date-header">-</div>
                            <div class="no-meal">다른 달</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    continue

                is_today = (
                    selected_year == now.year
                    and selected_month == now.month
                    and day == now.day
                )

                card_class = (
                    "meal-card meal-card-today" if is_today else "meal-card"
                )
                today_badge = (
                    "<span class='today-tag'>TODAY</span>" if is_today else ""
                )

                # 카드 HTML 시작
                card_html = f"""
                <div class="{card_class}">
                    <div class="date-header">
                        <span>{day}일 ({days_of_week[i][0]})</span>
                        {today_badge}
                    </div>
                """

                # 급식 데이터 유무 검사
                if day not in monthly_meals:
                    card_html += "<div class='no-meal'>😴 급식 없음</div>"
                else:
                    day_meals = monthly_meals[day]
                    displayed_any = False

                    for meal_type, meal_info in day_meals.items():
                        # 필터링 조건
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

                        # 칼로리 텍스트 구성
                        cal_str = (
                            f" <span class='calorie-text'>({meal_info['cal']})</span>"
                            if meal_info["cal"]
                            else ""
                        )

                        # 급식 종류별 색상 배지
                        if meal_type == "중식":
                            badge_html = f"<div class='badge-lunch'>🔵 {meal_type}{cal_str}</div>"
                        elif meal_type == "석식":
                            badge_html = f"<div class='badge-dinner'>🔴 {meal_type}{cal_str}</div>"
                        else:
                            badge_html = f"<div class='badge-other'>🟢 {meal_type}{cal_str}</div>"

                        # 메뉴 포맷팅 (알레르기 변환 + 형광펜 별표 하이라이트)
                        formatted_menu = format_menu_items(
                            meal_info["menu"], convert_allergy
                        )

                        card_html += (
                            f"{badge_html}<div>{formatted_menu}</div>"
                        )

                    if not displayed_any:
                        card_html += (
                            "<div class='no-meal'>🔍 해당 식단 없음</div>"
                        )

                card_html += "</div>"  # card 닫기

                st.markdown(card_html, unsafe_allow_html=True)

except Exception as e:
    st.error(f"🖥️ 화면을 구성하는 중에 오류가 발생했습니다: {e}")
