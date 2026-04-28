"""
score.py — 取得した記事をスコアリングしてTOP3を抽出する

【スコア計算式】
  score = (いいね × 1.0)
        + (コメント × 2.0)
        + (AIキーワード出現回数 × 3.0)
        + (ボーナスキーワード出現回数 × 5.0)
        + recency_bonus（新しさ加点）

  recency_bonus:
    24時間以内  → +30
    48時間以内  → +15
    7日以内     → +5
    それ以降    → 0
"""

from datetime import datetime, timezone, timedelta
from typing import Optional


# ============================================================
# 定数
# ============================================================

WEIGHT_LIKES    = 1.0   # いいね1件あたりの加点
WEIGHT_COMMENTS = 2.0   # コメント1件あたりの加点（議論を呼ぶ記事は重要）
WEIGHT_AI_KW    = 3.0   # AI必須キーワード1回あたりの加点
WEIGHT_BONUS_KW = 5.0   # ボーナスキーワード1回あたりの加点

RECENCY_24H  = 30       # 24時間以内の加点
RECENCY_48H  = 15       # 48時間以内の加点
RECENCY_7D   = 5        # 7日以内の加点


# ============================================================
# スコア計算
# ============================================================

def calc_recency_bonus(published_at: Optional[datetime]) -> int:
    """公開日時から新しさボーナスを計算する"""
    if published_at is None:
        return 0

    now = datetime.now(timezone.utc)

    # タイムゾーン情報がない場合はUTCとみなす
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)

    age = now - published_at

    if age <= timedelta(hours=24):
        return RECENCY_24H
    elif age <= timedelta(hours=48):
        return RECENCY_48H
    elif age <= timedelta(days=7):
        return RECENCY_7D
    else:
        return 0


def calc_score(article: dict) -> float:
    """
    1記事のスコアを計算して返す

    Args:
        article: fetch.py が返す記事辞書

    Returns:
        float: 合計スコア
    """
    likes    = article.get("likes", 0)
    comments = article.get("comments", 0)
    ai_kw    = article.get("ai_keyword_count", 0)
    bonus_kw = article.get("bonus_keyword_count", 0)
    pub_at   = article.get("published_at")

    score = (
        likes    * WEIGHT_LIKES
        + comments * WEIGHT_COMMENTS
        + ai_kw    * WEIGHT_AI_KW
        + bonus_kw * WEIGHT_BONUS_KW
        + calc_recency_bonus(pub_at)
    )

    # スコア内訳をデバッグ用に記事に付与
    article["_score_detail"] = {
        "likes_score":    likes * WEIGHT_LIKES,
        "comments_score": comments * WEIGHT_COMMENTS,
        "ai_kw_score":    ai_kw * WEIGHT_AI_KW,
        "bonus_kw_score": bonus_kw * WEIGHT_BONUS_KW,
        "recency_bonus":  calc_recency_bonus(pub_at),
        "total":          score,
    }

    return score


def rank_articles(articles: list[dict], top_n: int = 3) -> list[dict]:
    """
    記事リストをスコアリングして上位N件を返す。
    ソースの多様性を保証する（Zenn/Dev.to/note それぞれ最低1枠確保）。

    Args:
        articles: fetch.py が返す記事リスト
        top_n: 返す件数（デフォルト3）

    Returns:
        スコア降順でソートされた上位N件のリスト
    """
    if not articles:
        return []

    # 各記事にスコアを付与
    for article in articles:
        article["score"] = calc_score(article)

    # ソース別に最高スコア記事を1件ずつ確保
    sources = ["Zenn", "Dev.to", "note"]
    guaranteed: list[dict] = []
    seen_urls: set[str] = set()

    for src in sources:
        candidates = [a for a in articles if a["source"] == src]
        if candidates:
            best = max(candidates, key=lambda x: x["score"])
            guaranteed.append(best)
            seen_urls.add(best["url"])

    # 保証枠が top_n を超えた場合はスコア上位 top_n に絞る
    if len(guaranteed) >= top_n:
        result = sorted(guaranteed, key=lambda x: x["score"], reverse=True)[:top_n]
        return result

    # 残りの枠をスコア順で埋める（重複なし）
    remaining_slots = top_n - len(guaranteed)
    extras = sorted(
        [a for a in articles if a["url"] not in seen_urls],
        key=lambda x: x["score"],
        reverse=True,
    )[:remaining_slots]

    result = sorted(guaranteed + extras, key=lambda x: x["score"], reverse=True)
    return result


# ============================================================
# 動作確認用（サンプルデータでの実行結果）
# ============================================================

if __name__ == "__main__":
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)

    # ---- サンプルデータ ----
    sample_articles = [
        {
            "source": "Zenn",
            "title": "Claude 3.7のAIエージェント機能が凄すぎる件",
            "url": "https://zenn.dev/sample/articles/claude-agent",
            "likes": 320,
            "comments": 18,
            "published_at": now - timedelta(hours=5),   # 5時間前（24h以内）
            "lang": "ja",
            "ai_keyword_count": 4,   # AI, LLM, ChatGPT, AIエージェント
            "bonus_keyword_count": 3, # Anthropic, Claude × 2
        },
        {
            "source": "Dev.to",
            "title": "Building an LLM app with OpenAI and LangChain",
            "url": "https://dev.to/sample/llm-app",
            "likes": 210,
            "comments": 25,
            "published_at": now - timedelta(hours=30),  # 30時間前（48h以内）
            "lang": "en",
            "ai_keyword_count": 3,
            "bonus_keyword_count": 2, # OpenAI, Google
        },
        {
            "source": "note",
            "title": "生成AIで業務効率化してみた話",
            "url": "https://note.com/sample/n/genai",
            "likes": 0,
            "comments": 0,
            "published_at": now - timedelta(hours=10),  # 10時間前（24h以内）
            "lang": "ja",
            "ai_keyword_count": 2,   # AI, 生成AI
            "bonus_keyword_count": 0,
        },
        {
            "source": "Zenn",
            "title": "ChatGPTとGeminiを比較してみた【2025年版】",
            "url": "https://zenn.dev/sample/articles/gpt-vs-gemini",
            "likes": 150,
            "comments": 10,
            "published_at": now - timedelta(days=3),    # 3日前（7日以内）
            "lang": "ja",
            "ai_keyword_count": 3,
            "bonus_keyword_count": 3, # ChatGPT, Google, Gemini
        },
        {
            "source": "Dev.to",
            "title": "Getting started with AI in 2025",
            "url": "https://dev.to/sample/ai-2025",
            "likes": 80,
            "comments": 5,
            "published_at": now - timedelta(days=10),   # 10日前（加点なし）
            "lang": "en",
            "ai_keyword_count": 1,
            "bonus_keyword_count": 0,
        },
    ]

    # ---- スコアリング実行 ----
    print("=" * 60)
    print("📊 スコアリング結果")
    print("=" * 60)
    print(f"\n【計算式】")
    print(f"  score = いいね × {WEIGHT_LIKES}")
    print(f"        + コメント × {WEIGHT_COMMENTS}")
    print(f"        + AIキーワード出現数 × {WEIGHT_AI_KW}")
    print(f"        + ボーナスキーワード出現数 × {WEIGHT_BONUS_KW}")
    print(f"        + 新しさボーナス（24h:{RECENCY_24H} / 48h:{RECENCY_48H} / 7d:{RECENCY_7D} / それ以降:0）")

    print(f"\n{'No.':<4} {'ソース':<8} {'スコア':>7} │ {'いいね':>6} {'コメ':>5} {'AIkw':>5} {'Bkw':>5} {'新しさ':>6} │ タイトル")
    print("-" * 100)

    all_scored = sorted(sample_articles, key=lambda x: calc_score(x), reverse=True)
    for i, a in enumerate(all_scored, 1):
        d = a["_score_detail"]
        pub = a["published_at"].strftime("%m/%d %H:%M") if a["published_at"] else "不明"
        marker = "★" if i <= 3 else " "
        print(
            f"{marker}{i:<3} {a['source']:<8} {d['total']:>7.1f} │"
            f" {d['likes_score']:>6.1f} {d['comments_score']:>5.1f}"
            f" {d['ai_kw_score']:>5.1f} {d['bonus_kw_score']:>5.1f} {d['recency_bonus']:>6} │"
            f" {a['title'][:40]}"
        )

    print("\n" + "=" * 60)
    print("🏆 TOP 3 記事")
    print("=" * 60)
    top3 = rank_articles(sample_articles, top_n=3)
    for i, a in enumerate(top3, 1):
        d = a["_score_detail"]
        pub = a["published_at"].strftime("%Y-%m-%d %H:%M") if a["published_at"] else "不明"
        print(f"\n【{i}位】 {a['source']}  スコア: {d['total']:.1f}")
        print(f"  タイトル : {a['title']}")
        print(f"  URL      : {a['url']}")
        print(f"  公開日   : {pub}")
        print(f"  いいね: {a['likes']} | コメント: {a['comments']}")
        print(f"  内訳     : いいね({d['likes_score']:.0f}) + コメント({d['comments_score']:.0f})"
              f" + AIkw({d['ai_kw_score']:.0f}) + Bonuskw({d['bonus_kw_score']:.0f})"
              f" + 新しさ({d['recency_bonus']})")
