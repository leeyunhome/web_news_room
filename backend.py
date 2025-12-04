import os
import json
import base64
from datetime import datetime
import feedparser
from bs4 import BeautifulSoup
from github import Github, GithubException
from google import genai
from google.genai import types

class GitHubStorage:
    def __init__(self, token, repo_name):
        self.token = token
        self.repo_name = repo_name
        self.github = Github(token)
        self.repo = self.github.get_repo(repo_name)

    def load_json(self, path):
        try:
            content = self.repo.get_contents(path)
            decoded_content = base64.b64decode(content.content).decode('utf-8')
            return json.loads(decoded_content)
        except GithubException as e:
            if e.status == 404:
                return None
            raise e
        except Exception as e:
            print(f"Error loading {path}: {e}")
            return None

    def save_json(self, path, data, message):
        try:
            json_str = json.dumps(data, indent=2, ensure_ascii=False)
            
            try:
                content = self.repo.get_contents(path)
                self.repo.update_file(
                    path=path,
                    message=message,
                    content=json_str,
                    sha=content.sha
                )
            except GithubException as e:
                if e.status == 404:
                    self.repo.create_file(
                        path=path,
                        message=message,
                        content=json_str
                    )
                else:
                    raise e
            return True
        except Exception as e:
            print(f"Error saving {path}: {e}")
            return False

class NewsAnalyzer:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)

    def list_models(self):
        try:
            # The SDK might have different ways to list models depending on version
            # This is a best-effort attempt for google-genai SDK
            models = self.client.models.list()
            return [m.name for m in models]
        except Exception as e:
            return [f"Error listing models: {str(e)}"]

    def fetch_rss(self, urls):
        articles = []
        for url in urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    # Basic filtering to avoid too old news could be added here
                    # For now, just take the latest ones
                    summary = getattr(entry, 'summary', '')
                    if not summary and hasattr(entry, 'description'):
                        summary = entry.description
                    
                    # Clean HTML from summary
                    soup = BeautifulSoup(summary, 'html.parser')
                    clean_summary = soup.get_text()

                    articles.append({
                        'title': entry.title,
                        'link': entry.link,
                        'summary': clean_summary[:500], # Limit summary length
                        'published': getattr(entry, 'published', str(datetime.now()))
                    })
            except Exception as e:
                print(f"Error fetching {url}: {e}")
        return articles

    def analyze_news(self, articles):
        if not articles:
            return None

        # Limit to latest 20 articles to avoid Rate Limits (TPM)
        if len(articles) > 20:
            print(f"Too many articles ({len(articles)}). Limiting to top 20 for analysis.")
            articles = articles[:20]

        # Prepare prompt
        articles_text = ""
        for i, art in enumerate(articles):
            articles_text += f"{i+1}. 제목: {art['title']}\n   링크: {art['link']}\n   내용: {art['summary']}\n\n"

        prompt = f"""
        당신은 전문 IT 뉴스 에디터입니다. 아래 제공된 IT 뉴스 기사들을 분석하여 일일 브리핑을 작성해주세요.

        [기사 목록]
        {articles_text}

        [작성 규칙]
        1. 중복된 기사나 매우 유사한 내용은 하나로 통합하세요.
        2. 섹션을 두 개로 나누세요:
           - **헤드라인 (Headline)**: 가장 중요한 이슈 3~5개를 선정하여 각각 3줄 이내로 핵심을 요약하세요.
           - **단신 (Briefs)**: 그 외 주목할 만한 뉴스를 한 줄로 요약하여 나열하세요.
        3. 톤앤매너는 객관적이고 전문적으로 작성하세요.
        4. 각 요약 끝에는 반드시 원본 기사의 링크를 `[원문보기](URL)` 형태로 포함하세요.
        5. 출력 형식은 Markdown입니다.

        [출력 예시]
        ## 🚨 헤드라인
        ### 1. 구글, 새로운 AI 모델 Gemini 2.0 공개
        구글이 멀티모달 기능을 대폭 강화한 Gemini 2.0을 공개했습니다. ... [원문보기](http://...)

        ## 📰 단신
        * 애플, 차세대 아이폰 SE 생산 시작 루머 [원문보기](http://...)
        * ...
        """

        import time

        # Try Gemini 2.0 Flash (Stable) first
        try:
            response = self.client.models.generate_content(
                model='gemini-2.0-flash-001',
                contents=prompt
            )
            return response.text
        except Exception as e:
            error_msg = f"Error generating content (2.0-flash-001): {str(e)}"
            print(error_msg)
            
            # If Rate Limit (429), wait and retry
            if "429" in str(e):
                print("Rate limit hit. Waiting 30 seconds before retry...")
                time.sleep(30)
                try:
                    response = self.client.models.generate_content(
                        model='gemini-2.0-flash-001',
                        contents=prompt
                    )
                    return response.text
                except Exception as retry_e:
                    error_msg += f"\nRetry error (2.0-flash-001): {str(retry_e)}"
            
            # Fallback to 2.0 Flash Lite (likely higher quota/faster)
            try:
                print("Falling back to gemini-2.0-flash-lite-001...")
                response = self.client.models.generate_content(
                    model='gemini-2.0-flash-lite-001',
                    contents=prompt
                )
                return response.text
            except Exception as e2:
                error_msg += f"\nFallback error (2.0-flash-lite-001): {str(e2)}"
                print(f"Error generating content with fallback: {e2}")
                
                # List available models to help debugging
                try:
                    available_models = self.list_models()
                    error_msg += f"\n\n[Debug] Available Models: {', '.join(available_models)}"
                except:
                    pass
                
                return f"ERROR: {error_msg}"
