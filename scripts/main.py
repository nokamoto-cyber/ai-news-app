"""
main.py — 記事取得→スコアリング→要約→JSON出力 の一括実行スクリプト

実行方法:
  python scripts/main.py

出力先:
  public/data/articles.json
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

# スクリプトフォルダをパスに追加
sys.path.insert(0, os.path.dirname(__file__))

from fetch import fetch_all
from score import rank_articles, calc_score
from summarize import summarize_articles

# ============================================================
# 定数
# ============================================================

JST = timezone(timedelta(hours=9))
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "public", "data", "articles.json")

# トレンドキーワードとして抽出する候補
TREND_KEYWORDS = [
    "ChatGPT", "GPT", "Claude", "Gemini", "Copilot",
    "OpenAI", "Anthropic", "Google", "Microsoft",
    "LLM", "AIエージェント", "生成AI", "RAG",
    "マルチモーダル", "画像生成", "音声AI",
]


# ============================================================
# トレンドキーワード抽出
# ============================================================

def extract_trending_keywords(articles: list[dict], top_n: int = 5) -> list[str]:
    """全記事のタイトルと要約からキーワード出現回数を集計してTOP N を返す"""
    counts = {}
    for article in articles:
        text = " ".join([
            article.get("title", ""),
            article.get("title_ja", ""),
            " ".join(article.get("summary", [])),
            article.get("highlight", ""),
        ]).upper()

        for kw in TREND_KEYWORDS:
            if kw.upper() in text:
                counts[kw] = counts.get(kw, 0) + 1

    sorted_kw = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [kw for kw, _ in sorted_kw[:top_n]]


# ============================================================
# メイン処理
# ============================================================

def run():
    print("=" * 55)
    print("🚀 AI ニュースアプリ — データ更新開始")
    print(f"   {datetime.now(JST).strftime('%Y-%m-%d %H:%M')} (JST)")
    print("=" * 55)

    # Step 1: 記事取得
    all_articles = fetch_all()
    if not all_articles:
        print("⚠️  記事が1件も取得できませんでした。処理を終了します。")
        return False

    # Step 2: スコアリング → TOP3 抽出
    print("\n📊 スコアリング中...")
    for a in all_articles:
        a["score"] = calc_score(a)
    top3 = rank_articles(all_articles, top_n=3)
    for i, a in enumerate(top3, 1):
        a["rank"] = i
        print(f"  [{i}位] {a['source']:6s} score={a['score']:.0f}  {a['title'][:45]}")

    # Step 3: 要約・翻訳（Gemini API）
    top3 = summarize_articles(top3)

    # Step 4: トレンドキーワード抽出
    trending = extract_trending_keywords(top3)
    print(f"\n🔥 トレンドキーワード: {', '.join(trending)}")

    # Step 5: JSON出力
    now_jst = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    output = {
        "updated_at": now_jst,
        "articles": [_to_output(a) for a in top3],
        "trending_keywords": trending,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完了！ → {OUTPUT_PATH}")
    print(f"   更新時刻: {now_jst}")
    print("=" * 55)
    return True


def _to_output(a: dict) -> dict:
    """記事辞書を出力JSON用に整形する"""
    pub = a.get("published_at")
    return {
        "rank":          a.get("rank", 1),
        "source":        a.get("source", ""),
        "title":         a.get("title", ""),
        "title_ja":      a.get("title_ja", a.get("title", "")),
        "url":           a.get("url", ""),
        "likes":         a.get("likes", 0),
        "comments":      a.get("comments", 0),
        "published_at":  pub.strftime("%Y-%m-%d") if pub else "",
        "lang":          a.get("lang", "ja"),
        "score":         round(a.get("score", 0), 1),
        "summary":       a.get("summary", []),
        "highlight":     a.get("highlight", ""),
    }


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
