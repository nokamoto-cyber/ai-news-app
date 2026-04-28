"""
fetch.py — note / Zenn / Dev.to からAI関連記事を取得する
"""

import requests
import feedparser
from datetime import datetime, timezone, timedelta
from typing import Optional
import re

# ============================================================
# 定数：キーワード定義
# ============================================================

# 必須キーワード（いずれか1つ以上がタイトルまたは本文に含まれること）
REQUIRED_KEYWORDS = ["AI", "生成AI", "LLM", "ChatGPT", "AIエージェント"]

# ボーナスキーワード（含まれるとスコア加点）
BONUS_KEYWORDS = ["OpenAI", "Anthropic", "Google", "Gemini", "Claude", "Copilot"]

# タイムゾーン（日本標準時）
JST = timezone(timedelta(hours=9))


# ============================================================
# ユーティリティ関数
# ============================================================

def contains_required_keyword(text: str) -> bool:
    """必須キーワードをいずれか1つ以上含むか判定（大文字小文字を区別しない）"""
    text_upper = text.upper()
    for kw in REQUIRED_KEYWORDS:
        if kw.upper() in text_upper:
            return True
    return False


def count_ai_keywords(text: str) -> int:
    """必須キーワードの合計出現回数を返す（薄い記事の除外に使用）"""
    text_upper = text.upper()
    count = 0
    for kw in REQUIRED_KEYWORDS:
        count += text_upper.count(kw.upper())
    return count


def count_bonus_keywords(text: str) -> int:
    """ボーナスキーワードの合計出現回数を返す"""
    text_upper = text.upper()
    count = 0
    for kw in BONUS_KEYWORDS:
        count += text_upper.count(kw.upper())
    return count


def parse_iso_datetime(dt_str: str) -> Optional[datetime]:
    """ISO 8601形式の日付文字列をdatetimeオブジェクトに変換"""
    if not dt_str:
        return None
    try:
        # Python 3.11以降は fromisoformat が Z に対応
        dt_str = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


def is_valid_article(title: str, body: str) -> tuple[bool, str]:
    """
    記事の有効性チェック
    Returns: (有効か, 除外理由)
    """
    combined = f"{title} {body}"

    # 必須キーワードがない → 除外
    if not contains_required_keyword(combined):
        return False, "必須キーワードなし"

    # キーワード1回のみ かつ タイトルにも含まれない → 薄い記事として除外
    if count_ai_keywords(combined) == 1 and not contains_required_keyword(title):
        return False, "キーワード頻度が低い（本文1回のみ）"

    return True, ""


# ============================================================
# Zenn 記事取得
# ============================================================

def fetch_zenn(max_articles: int = 30) -> list[dict]:
    """
    Zenn の公開API から AI関連記事を取得する
    API: https://zenn.dev/api/articles?order=liked_count&topicname=ai
    """
    print("📥 Zenn から記事取得中...")
    articles = []

    try:
        url = "https://zenn.dev/api/articles"
        params = {
            "order": "liked_count",
            "topicname": "ai",
            "count": max_articles,
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("articles", []):
            title = item.get("title", "")
            slug = item.get("slug", "")
            username = item.get("user", {}).get("username", "")
            article_url = f"https://zenn.dev/{username}/articles/{slug}"
            likes = item.get("liked_count", 0)
            comments = item.get("comments_count", 0)
            published_at = parse_iso_datetime(item.get("published_at", ""))

            # キーワードチェック（Zenn APIは本文を返さないのでタイトルのみ）
            valid, reason = is_valid_article(title, "")
            if not valid:
                continue

            articles.append({
                "source": "Zenn",
                "title": title,
                "url": article_url,
                "likes": likes,
                "comments": comments,
                "published_at": published_at,
                "lang": "ja",
                "bonus_keyword_count": count_bonus_keywords(title),
                "ai_keyword_count": count_ai_keywords(title),
            })

        print(f"  ✅ Zenn: {len(articles)} 件取得")
    except Exception as e:
        print(f"  ❌ Zenn 取得エラー: {e}")

    return articles


# ============================================================
# Dev.to 記事取得
# ============================================================

def fetch_devto(max_articles: int = 30) -> list[dict]:
    """
    Dev.to の公開REST API から AI関連記事を取得する
    API: https://dev.to/api/articles?tag=ai
    """
    print("📥 Dev.to から記事取得中...")
    articles = []

    # 複数タグで検索して重複排除
    tags = ["ai", "llm", "chatgpt", "generativeai"]
    seen_urls = set()

    try:
        for tag in tags:
            url = "https://dev.to/api/articles"
            params = {
                "tag": tag,
                "per_page": max_articles // len(tags),
                "top": 7,  # 直近7日間の人気記事
            }
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()

            for item in resp.json():
                article_url = item.get("url", "")
                if article_url in seen_urls:
                    continue
                seen_urls.add(article_url)

                title = item.get("title", "")
                description = item.get("description", "")
                likes = item.get("positive_reactions_count", 0)
                comments = item.get("comments_count", 0)
                published_at = parse_iso_datetime(item.get("published_at", ""))

                combined = f"{title} {description}"
                valid, reason = is_valid_article(title, description)
                if not valid:
                    continue

                articles.append({
                    "source": "Dev.to",
                    "title": title,
                    "url": article_url,
                    "likes": likes,
                    "comments": comments,
                    "published_at": published_at,
                    "lang": "en",
                    "bonus_keyword_count": count_bonus_keywords(combined),
                    "ai_keyword_count": count_ai_keywords(combined),
                })

        print(f"  ✅ Dev.to: {len(articles)} 件取得")
    except Exception as e:
        print(f"  ❌ Dev.to 取得エラー: {e}")

    return articles


# ============================================================
# note 記事取得
# ============================================================

def fetch_note(max_articles: int = 30) -> list[dict]:
    """
    note の RSS フィードから AI関連記事を取得する
    RSS: https://note.com/hashtag/AI.rss
    ※ note は RSS 経由のためいいね数・コメント数は取得不可
    """
    print("📥 note から記事取得中...")
    articles = []

    # 複数ハッシュタグのRSSを確認
    # note の正しいRSS URL形式: https://note.com/hashtag/{tag}/rss
    hashtags = ["AI", "生成AI", "LLM", "ChatGPT"]
    seen_urls = set()

    try:
        for tag in hashtags:
            feed_url = f"https://note.com/hashtag/{tag}/rss"
            feed = feedparser.parse(feed_url)

            for entry in feed.entries[:max_articles // len(hashtags)]:
                article_url = entry.get("link", "")
                if article_url in seen_urls:
                    continue
                seen_urls.add(article_url)

                title = entry.get("title", "")
                # RSS の summary タグから本文の一部を取得
                summary = re.sub(r"<[^>]+>", "", entry.get("summary", ""))

                # 公開日のパース（feedparser は time_struct で返す）
                published_at = None
                if entry.get("published_parsed"):
                    published_at = datetime(
                        *entry.published_parsed[:6], tzinfo=timezone.utc
                    )

                combined = f"{title} {summary}"
                valid, reason = is_valid_article(title, summary)
                if not valid:
                    continue

                articles.append({
                    "source": "note",
                    "title": title,
                    "url": article_url,
                    "likes": 0,       # note RSSでは取得不可
                    "comments": 0,    # note RSSでは取得不可
                    "published_at": published_at,
                    "lang": "ja",
                    "bonus_keyword_count": count_bonus_keywords(combined),
                    "ai_keyword_count": count_ai_keywords(combined),
                })

        print(f"  ✅ note: {len(articles)} 件取得")
    except Exception as e:
        print(f"  ❌ note 取得エラー: {e}")

    return articles


# ============================================================
# 全ソース統合
# ============================================================

def fetch_all() -> list[dict]:
    """全ソースから記事を取得して統合する"""
    print("=" * 50)
    print("🚀 記事取得開始")
    print("=" * 50)

    zenn_articles = fetch_zenn()
    devto_articles = fetch_devto()
    note_articles = fetch_note()

    all_articles = zenn_articles + devto_articles + note_articles

    print("-" * 50)
    print(f"📊 合計取得数: {len(all_articles)} 件")
    print(f"   Zenn: {len(zenn_articles)} 件")
    print(f"   Dev.to: {len(devto_articles)} 件")
    print(f"   note: {len(note_articles)} 件")
    print("=" * 50)

    return all_articles


# ============================================================
# 動作確認用
# ============================================================

if __name__ == "__main__":
    articles = fetch_all()

    print("\n📋 取得記事サンプル（先頭5件）:")
    for i, a in enumerate(articles[:5], 1):
        pub = a["published_at"].strftime("%Y-%m-%d") if a["published_at"] else "不明"
        print(f"\n[{i}] {a['source']} | {pub}")
        print(f"  タイトル : {a['title'][:60]}")
        print(f"  URL      : {a['url'][:60]}")
        print(f"  いいね   : {a['likes']} | コメント: {a['comments']}")
        print(f"  言語     : {a['lang']}")
        print(f"  AIキーワード: {a['ai_keyword_count']}回 | ボーナス: {a['bonus_keyword_count']}回")
