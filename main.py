import calendar
from datetime import datetime
import os
import re
import pandas as pd
import streamlit as st

# ==========================================
# 1. 페이지 설정 및 커스텀 CSS (스타일링)
# ==========================================
st.set_page_config(
    page_title="한 달치 학교 급식 달력 🍱", page_icon="🍱", layout="wide"
)

# 텍스트 및 형광펜 스타일
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
    
    /* ⭐ 인기 메뉴 형광펜 하이라이트 */
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
# 2. 알레르기 매핑 및 형광펜 키워드
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
    "파이",
    "아이스티",
    "아이스크림",
    "젤리",
    "요거트",
    "떡",
    "그라탕",
    "훈제",
    "골뱅이",
    "오징어",
]


# ==========================================
# 3. 헬퍼 함수 (메뉴 파싱)
# ==========================================
def format_menu_items(menu_str, convert_allergy=False):
    """메뉴 문자열을 라인별로 정제하고 알레르기 변환 및 형광펜 강조 적용"""
    if pd.isna(menu_str):
        return ""

    lines = str(menu_str).split("<br/>")
    formatted_list = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 특수 기호(&, && 등) 정리
        clean_line = re.sub(r"^&+", "", line).strip()

        # 알레르기 변환
        if convert_allergy:

            def replace_allergy(match):
                numbers = match.group(1).split(".")
                names = [ALLERGY_MAP.get(num, num) for num in numbers if num]
                return (
                    f" <span class='allergy-info'>({', '.join(names)})</span>"
                )

            clean_line = re.sub(r"\(([\d\.]+)\)", replace_allergy, clean_line)

        # 형광펜 키워드 포함 검사
        is_special = any(keyword in clean_line for keyword in SPECIAL_KEYWORDS)

        if is_special:
            item_html = f"<div class='menu-item'>⭐ <span class='highlight-yummy'>{clean_line}</span></div>"
        else:
            item_html = f"<div class='menu-item'>• {clean_line}</div>"

        formatted_list.append(item_html)

    return "".join(formatted_list)


@st.cache_data
def load_csv_meals(file_path):
    """CSV 파일에서 데이터를 읽어 날짜별로 정리합니다."""
    if not os.path.exists(file_path):
        return None, "파일을 찾을 수 없습니다."

    try:
        df = pd.read_csv(file_path)

        # 날짜 포맷 정리 (YYYYMMDD -> datetime)
        df["급식일자"] = df["급식일자"].astype(str)
        monthly_meals = {}

        for _, row in df.iterrows():
            ymd = row["급식일자"]
            if len(ymd) == 8:
                year = int(ymd[:4])
                month = int(ymd[4:6])
                day = int(ymd[6:8])

                meal_type = str(row["식사명"]).strip()  # 중식, 석식 등
                menu_text = row["요리명"]

                # 칼로리 정보 정제
                cal_raw = str(row.get("칼로리정보", ""))
                cal_match = re.search(r"([\d\.]+\s*Kcal)", cal_raw)
                cal_str = cal_match.group(1) if cal_match else ""

                if (year, month) not in monthly_meals:
                    monthly_meals[(year, month)] = {}
                if day not in monthly_meals[(year, month)]:
                    monthly_meals[(year, month)][day] = {}

                monthly_meals[(year, month)][day][meal_type] = {
                    "menu": menu_text,
                    "cal": cal_str,
                    "school_name": row.get("학교명", "학교"),
                }

        return monthly_meals, None
    except Exception as e:
        return None, f"CSV 로드 중 오류 발생: {e}"


# ==========================================
# 4. 데이터 로드 및 상단 컨트롤
# ==========================================
csv_filename = "급식식단정보.csv"
monthly_meals, error_msg = load_csv_meals(csv_filename)

if error_msg:
    st.error(f"🚨 {error_msg}")
    st.stop()

st.title("🍱 한 달치 학교 급식 달력")

# 사이드바 설정
st.sidebar.title("⚙️ 설정 및 안내")
convert_allergy = st.sidebar.toggle(
    "알레르기 식품명으로 변환",
    value=False,
    help="메뉴 옆의 숫자를 실제 식재료 이름으로 바꿉니다.",
)

with st.sidebar.expander("ℹ️ 알레르기 번호 안내표"):
    for code, name in ALLERGY_MAP.items():
        st.write(f"**{code}번**: {name}")

# 연도/월 선택 영역
available_years = sorted(list(set([k[0] for k in monthly_meals.keys()])))
selected_year = (
    available_years[0] if available_years else datetime.now().year
)

available_months = sorted(
    list(
        set(
            [
                k[1]
                for k in monthly_meals.keys()
                if k[0] == selected_year
            ]
        )
    )
)
selected_month = (
    available_months[0] if available_months else datetime.now().month
)

col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    selected_year = st.selectbox(
        "연도 선택", available_years, index=0 if available_years else 0
    )
with col2:
    selected_month = st.selectbox(
        "월 선택", available_months, index=0 if available_months else 0
    )
with col3:
    meal_filter = st.radio(
        "급식 종류 필터",
        ["전체 보기", "중식만 보기", "석식만 보기"],
        horizontal=True,
    )

st.markdown("---")


# ==========================================
# 5. 달력 화면 렌더링 (안정적인 레이아웃)
# ==========================================
current_month_data = monthly_meals.get((selected_year, selected_month), {})

# 학교 이름 표시
school_name = "학교"
for d in current_month_data.values():
    for m in d.values():
        school_name = m.get("school_name", "학교")
        break
    break

st.subheader(f"🏫 {school_name} - {selected_year}년 {selected_month}월 급식표")

now = datetime.now()
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
            # 주말/다른 달 날짜 처리
            if day == 0:
                st.caption(f"{days_of_week[i]}")
                st.info("다른 달")
                continue

            is_today = (
                selected_year == now.year
                and selected_month == now.month
                and day == now.day
            )

            # 테두리가 있는 안전한 카드 구조
            with st.container(border=True):
                today_tag = " 🔥 **TODAY**" if is_today else ""
                st.markdown(f"**{day}일 ({days_of_week[i][0]})**{today_tag}")

                if day not in current_month_data:
                    st.caption("😴 급식 없음")
                else:
                    day_meals = current_month_data[day]
                    displayed_any = False

                    # 중식 -> 석식 순 정렬
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

                        # 칼로리 표시
                        cal_html = (
                            f" <span class='calorie-text'>({meal_info['cal']})</span>"
                            if meal_info["cal"]
                            else ""
                        )

                        if meal_type == "중식":
                            st.markdown(
                                f"<div class='badge-lunch'>🔵 {meal_type}{cal_html}</div>",
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown(
                                f"<div class='badge-dinner'>🔴 {meal_type}{cal_html}</div>",
                                unsafe_allow_html=True,
                            )

                        # 메뉴 포맷팅
                        formatted_menu = format_menu_items(
                            meal_info["menu"], convert_allergy
                        )
                        st.markdown(formatted_menu, unsafe_allow_html=True)

                    if not displayed_any:
                        st.caption("🔍 해당 식단 없음")
