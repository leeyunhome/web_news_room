import streamlit as st
import os
import json
from datetime import datetime
from dotenv import load_dotenv
from backend import GitHubStorage, NewsAnalyzer

# Load environment variables
load_dotenv()

# Page Config
st.set_page_config(
    page_title="Personal AI IT Newsroom",
    page_icon="📰",
    layout="wide"
)

# Initialize Session State
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# Load Secrets
try:
    GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
    REPO_NAME = st.secrets.get("REPO_NAME") or os.getenv("REPO_NAME")
    GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD")
except FileNotFoundError:
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    REPO_NAME = os.getenv("REPO_NAME")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# Initialize Backend
if not GITHUB_TOKEN or not REPO_NAME or not GEMINI_API_KEY:
    st.error("🚨 환경 변수 또는 Secrets가 설정되지 않았습니다. (GITHUB_TOKEN, REPO_NAME, GEMINI_API_KEY)")
    st.stop()

storage = GitHubStorage(GITHUB_TOKEN, REPO_NAME)
analyzer = NewsAnalyzer(GEMINI_API_KEY)

# --- Sidebar ---
st.sidebar.title("🔧 Menu")
menu = st.sidebar.radio("Go to", ["Newsroom", "Admin Dashboard"])

# --- Admin Authentication ---
if menu == "Admin Dashboard":
    if not st.session_state.authenticated:
        password = st.sidebar.text_input("Enter Admin Password", type="password")
        if st.sidebar.button("Login"):
            if password == ADMIN_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.sidebar.error("Incorrect Password")
        st.stop()
    
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()

# --- Functions ---
def load_data():
    feeds = storage.load_json("data/feeds.json") or {"urls": []}
    archive = storage.load_json("data/news_archive.json") or {}
    stats = storage.load_json("data/stats.json") or {"total_visits": 0, "log": []}
    return feeds, archive, stats

def save_stats(stats):
    storage.save_json("data/stats.json", stats, "Update visitor stats")

# --- Page: Newsroom (Public) ---
if menu == "Newsroom":
    st.title("📰 Personal AI IT Newsroom")
    st.caption("Google Gemini가 매일 아침 정리해주는 나만의 IT 뉴스 브리핑")

    feeds, archive, stats = load_data()

    # Update Stats
    stats["total_visits"] += 1
    stats["log"].append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    # Note: In a real high-traffic app, writing to git on every visit is bad. 
    # But for a personal app, it's acceptable or we can skip it for now to save API calls.
    # save_stats(stats) 

    # Date Selector
    dates = sorted(archive.keys(), reverse=True)
    if not dates:
        st.info("아직 생성된 뉴스 브리핑이 없습니다.")
    else:
        selected_date = st.selectbox("📅 날짜 선택", dates)
        
        if selected_date:
            news_data = archive[selected_date]
            st.markdown(f"### {selected_date} 브리핑")
            st.markdown("---")
            st.markdown(news_data['content'])
            
            with st.expander("🔍 원본 기사 목록 보기"):
                for item in news_data.get('raw_data', []):
                    st.markdown(f"- **[{item['title']}]({item['link']})**")
                    st.caption(f"{item['summary'][:100]}...")

# --- Page: Admin Dashboard ---
elif menu == "Admin Dashboard":
    st.title("⚙️ Admin Dashboard")
    
    feeds, archive, stats = load_data()

    # Tab 1: RSS Management
    tab1, tab2, tab3 = st.tabs(["RSS Feeds", "News Generation", "Statistics"])

    with tab1:
        st.subheader("RSS Feed Management")
        
        # List existing feeds
        if feeds['urls']:
            for i, url in enumerate(feeds['urls']):
                col1, col2 = st.columns([4, 1])
                col1.text(url)
                if col2.button("Delete", key=f"del_{i}"):
                    feeds['urls'].pop(i)
                    storage.save_json("data/feeds.json", feeds, "Remove RSS feed")
                    st.rerun()
        else:
            st.info("등록된 RSS 피드가 없습니다.")

        # Add new feed
        new_url = st.text_input("Add New RSS URL")
        if st.button("Add Feed"):
            if new_url and new_url not in feeds['urls']:
                feeds['urls'].append(new_url)
                if storage.save_json("data/feeds.json", feeds, "Add RSS feed"):
                    st.success("RSS 피드가 추가되었습니다.")
                    st.rerun()
                else:
                    st.error("저장 실패")
            elif new_url in feeds['urls']:
                st.warning("이미 등록된 URL입니다.")

    with tab2:
        st.subheader("News Generation")
        
        if st.button("🔍 Check Available Models"):
            with st.spinner("Checking models..."):
                models = analyzer.list_models()
                st.write("Available Models:")
                st.json(models)

        if st.button("🚀 Analyze News Now"):
            with st.spinner("RSS 피드 수집 및 Gemini 분석 중..."):
                # 1. Collect
                articles = analyzer.fetch_rss(feeds['urls'])
                st.write(f"수집된 기사 수: {len(articles)}개")
                
                if articles:
                    # 2. Analyze
                    summary = analyzer.analyze_news(articles)
                    
                    if summary:
                        if summary.startswith("ERROR:"):
                            st.error(f"Gemini 분석 실패:\n{summary}")
                        else:
                            # 3. Save
                            today = datetime.now().strftime("%Y-%m-%d")
                            archive[today] = {
                                "content": summary,
                                "raw_data": articles,
                                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }
                            
                            if storage.save_json("data/news_archive.json", archive, f"Add news for {today}"):
                                st.success(f"{today} 뉴스 브리핑 생성 완료!")
                                st.markdown(summary)
                            else:
                                st.error("GitHub 저장 실패")
                    else:
                        st.error("Gemini 분석 실패 (응답 없음)")
                else:
                    st.warning("수집된 기사가 없습니다. RSS 피드를 확인하세요.")

        st.subheader("Manage Archives")
        if archive:
            date_to_delete = st.selectbox("삭제할 날짜 선택", sorted(archive.keys(), reverse=True))
            if st.button("Delete Archive"):
                del archive[date_to_delete]
                storage.save_json("data/news_archive.json", archive, f"Delete news for {date_to_delete}")
                st.success("삭제되었습니다.")
                st.rerun()

    with tab3:
        st.subheader("Visitor Statistics")
        st.metric("Total Visits", stats['total_visits'])
        
        if stats['log']:
            st.dataframe(stats['log'], column_config={"0": "Visit Time"})
