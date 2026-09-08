import calendar
from datetime import datetime
import re
import requests
import streamlit as st

# ==========================================
# 1. 기본 설정 및 알레르기 정보 정의
# ==========================================
st.set_page_config(
    page_title="한 달치 학교 급식 달력", page_icon="🍱", layout="wide"
)

# 알레르기 번호 매핑 (1~19번)
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


# ==========================================
# 2. 헬퍼 함수
# ==========================================
def parse_menu(menu_str, convert_allergy=False):
    """급식 메뉴 문자열에서 알레르기 번호를 추출하거나 이름으로 변환합니다."""
    # NEIS API 결과의 <br/> 태그를 줄바꿈으로 변경
    clean_text = menu_str.replace("<br/>", "\n")

    if not convert_allergy:
        return clean_text

    def replace_allergy(match):
        numbers = match.group(1).split(".")
        names = [ALLERGY_MAP.get(num, num) for num in numbers if num]
        return f" ({', '.join(names)})"

    # 메뉴 이름 뒤의 괄호 안 숫자를 식재료 이름으로 변환
    pattern = r"\(([\d\.]+)\)"
    converted = re.sub(pattern, replace_allergy, clean_text)
    return converted


@st.cache_data(ttl=3600)
def fetch_month_meals(office_code, school_code, year, month, api_key):
    """NEIS API에서 지정된 월의 전체 급식 데이터를 조회합니다."""
    # 해당 월의 마지막 날 구하기
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

        # NEIS API 응답 검증
        if "mealServiceDietInfo" in data:
            return data["mealServiceDietInfo"][1]["row"], None
        elif "RESULT" in data:
            # 데이터가 없는 경우 (예: 방학 등)
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
# 3. 사이드바 구성
# ==========================================
st.sidebar.title("⚙️ 설정 및 안내")

# API 키 확인
if "NEIS_KEY" not in st.secrets:
    st.error(
        "⚠️ `secrets.toml`에 `NEIS_KEY`가 설정되지 않았습니다.\n.streamlit/secrets.toml 파일에 키를 추가해 주세요."
    )
    st.stop()

api_key = st.secrets["NEIS_KEY"]

# 학교 정보 입력창 (서울시교육청, 서울고등학교 기본값 예시)
office_code = st.sidebar.text_input("시도교육청코드", value="B10")
school_code = st.sidebar.text_input("표준학교코드", value="7010537")

st.sidebar.markdown("---")

# 알레르기 변환 옵션
convert_allergy = st.sidebar.toggle(
    "알레르기 식품명으로 변환",
    value=False,
    help="메뉴 옆의 숫자를 실제 식재료 이름으로 바꿉니다.",
)

# 알레르기 대응표 (접이식)
with st.sidebar.expander("ℹ️ 알레르기 번호 안내표"):
    for code, name in ALLERGY_MAP.items():
        st.write(f"**{code}번**: {name}")


# ==========================================
# 4. 상단 필터 및 화면 메인 구성
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
# 5. 데이터 불러오기 및 처리
# ==========================================
meal_raw_data, error_msg = fetch_month_meals(
    office_code, school_code, selected_year, selected_month, api_key
)

if error_msg:
    st.error(f"🚨 {error_msg}")
    st.stop()

# 날짜별, 급식종류별 데이터 매핑 구조 생성 {일(int): {급식명: 메뉴}}
# 예: {15: {'중식': '쌀밥<br/>김치...', '석식': '볶음밥...'}}
monthly_meals = {}
if meal_raw_data:
    for row in meal_raw_data:
        try:
            day = int(row["MLSV_YMD"][6:8])
            meal_name = row["MMEAL_SC_NM"]  # 조식, 중식, 석식 등
            menu_text = row["DDISH_NM"]

            if day not in monthly_meals:
                monthly_meals[day] = {}
            monthly_meals[day][meal_name] = menu_text
        except Exception as e:
            st.error(f"데이터 파싱 실패: {e}")


# ==========================================
# 6. 달력 화면 렌더링
# ==========================================
try:
    # 월~금(평일) 기반 달력 구조 가져오기 (0:월 ~ 6:일)
    month_cal = calendar.monthcalendar(selected_year, selected_month)

    days_of_week = ["월요일", "화요일", "수요일", "목요일", "금요일"]

    # 주차별로 달력 렌더링
    for week_idx, week in enumerate(month_cal):
        # 주말(토, 일)을 제외한 평일(월~금) 데이터만 추출
        workdays = week[:5]

        # 주에 평일 날짜가 하나라도 존재하는 경우에만 표시
        if sum(workdays) == 0:
            continue

        st.subheader(f"🗓️ {week_idx + 1}주차")
        cols = st.columns(5)

        for i, day in enumerate(workdays):
            with cols[i]:
                # 날짜 헤더 영역
                if day == 0:
                    st.caption(f"{days_of_week[i]}")
                    st.info("다른 달")
                    continue

                is_today = (
                    selected_year == now.year
                    and selected_month == now.month
                    and day == now.day
                )
                today_badge = " 🔥 TODAY" if is_today else ""
                header_text = f"**{day}일 ({days_of_week[i][0]})**{today_badge}"

                # 카드 테두리 스타일을 위한 container
                with st.container(border=True):
                    st.markdown(header_text)

                    # 급식 데이터 존재 여부 확인
                    if day not in monthly_meals:
                        st.caption("급식 없음")
                    else:
                        day_meals = monthly_meals[day]
                        displayed_any = False

                        # 급식 종류별 렌더링
                        for meal_type, menu_content in day_meals.items():
                            # 필터링 조건 적용
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

                            # 급식 종류별 배지 색상 구분
                            if meal_type == "중식":
                                badge_color = "🔵"
                            elif meal_type == "석식":
                                badge_color = "🔴"
                            else:
                                badge_color = "🟢"

                            st.markdown(f"**{badge_color} {meal_type}**")

                            # 메뉴 파싱 및 출력
                            formatted_menu = parse_menu(
                                menu_content, convert_allergy
                            )
                            st.text(formatted_menu)

                        # 필터 선택으로 인해 해당 날짜에 표시될 식단이 없는 경우
                        if not displayed_any:
                            st.caption("해당 식단 없음")

except Exception as e:
    st.error(f"🖥️ 화면을 구성하는 중에 오류가 발생했습니다: {e}")
