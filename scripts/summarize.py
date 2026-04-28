"""
summarize.py — 記事を要約・翻訳して非エンジニア向けの説明を生成する

使用API: Google Gemini API（無料枠）
  - 無料枠: 1日1500リクエスト / 1分15リクエスト
  - APIキー取得: https://aistudio.google.com/app/apikey

出力形式（JSON固定）:
{
  "title_ja": "日本語タイトル",
  "summary": ["1行目", "2行目", "3行目"],
  "highlight": "何がすごいか1行"
}
"""

import os
import json
import time
import re
from typing import Optional
from google import genai
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# 定数
# ============================================================

MODEL = "gemini-2.0-flash"   # 無料枠対応・高速モデル
MAX_RETRIES = 3
RETRY_WAIT_SEC = 2


# ============================================================
# プロンプト生成
# ============================================================

def build_prompt(title: str, content: str, lang: str) -> str:
    """
    記事情報からGeminiへのプロンプトを生成する。
    lang == "en" の場合は翻訳指示を追加。
    """
    translation_note = (
        "※この記事は英語です。すべて自然な日本語に翻訳してから回答してください。\n\n"
        if lang == "en" else ""
    )

    # 本文が長い場合は先頭1500文字に制限
    truncated = content[:1500] + "…（省略）" if len(content) > 1500 else content

    return f"""{translation_note}以下のAI記事を読んで、ITに詳しくない一般の人に向けて日本語で説明してください。

---
タイトル: {title}
本文:
{truncated}
---

【回答ルール】
- JSONのみ出力。説明文・前置き・```json などのコードブロックは不要
- summaryは各行20〜40文字
- highlightは「〜できるようになった」「〜が変わる」など変化・インパクトが伝わる1文
- 難しい技術用語は使わず、中学生でもわかる言葉で書く
- 「何がすごいのか」「自分の生活にどう関係するか」が伝わる内容にする

【必ずこのJSONのみ出力】
{{
  "title_ja": "日本語タイトル（英語なら翻訳、日本語ならそのまま）",
  "summary": [
    "1行目：この記事が伝えていること",
    "2行目：具体的に何が変わるか・何ができるか",
    "3行目：どんな人に関係するか・今後どうなるか"
  ],
  "highlight": "何がすごいかを1行で（例：誰でもAIで〇〇できるようになった）"
}}"""


# ============================================================
# JSONの抽出ユーティリティ
# ============================================================

def extract_json(text: str) -> dict:
    """
    モデルの出力テキストからJSONを抽出してパースする。
    ```json ... ``` 形式や余計なテキストが混入しても対応。
    """
    text = re.sub(r"```(?:json)?", "", text).strip()
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError(f"JSONが見つかりません。応答: {text[:200]}")
    return json.loads(match.group())


# ============================================================
# メイン処理：1記事を要約・翻訳
# ============================================================

def summarize_article(
    title: str,
    content: str,
    url: str,
    lang: str,
    client: Optional[genai.Client] = None,
) -> dict:
    """
    1記事を要約・翻訳して辞書で返す。

    Args:
        title:   記事タイトル
        content: 記事本文（なければ空文字でOK）
        url:     記事URL（エラーログ用）
        lang:    "ja" または "en"
        client:  genai.Client インスタンス（省略時は自動生成）

    Returns:
        {"title_ja": str, "summary": [str, str, str], "highlight": str}
        エラー時はフォールバック値を返す
    """
    if client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY が設定されていません。\n"
                "取得方法: https://aistudio.google.com/app/apikey\n"
                ".env ファイルに GEMINI_API_KEY=AIza... を追加してください。"
            )
        client = genai.Client(api_key=api_key)

    prompt = build_prompt(title, content, lang)
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
            )
            raw_text = response.text.strip()
            result = extract_json(raw_text)

            # 必須フィールドの検証
            assert "title_ja" in result, "title_ja がありません"
            assert isinstance(result.get("summary"), list) and len(result["summary"]) == 3, \
                "summary は3要素のリストが必要です"
            assert "highlight" in result, "highlight がありません"

            return result

        except json.JSONDecodeError as e:
            last_error = f"JSONパースエラー: {e}"
        except AssertionError as e:
            last_error = f"バリデーションエラー: {e}"
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"

        if attempt < MAX_RETRIES:
            print(f"  ⚠️  試行{attempt}/{MAX_RETRIES} 失敗: {last_error} → リトライ...")
            time.sleep(RETRY_WAIT_SEC)

    print(f"  ❌ 要約失敗: {url[:60]}\n     理由: {last_error}")
    return _fallback(title, lang)


def _fallback(title: str, lang: str) -> dict:
    """全リトライ失敗時のフォールバック"""
    return {
        "title_ja": title if lang == "ja" else f"[翻訳失敗] {title}",
        "summary": [
            "記事の要約を取得できませんでした。",
            "元記事をクリックして内容をご確認ください。",
            "しばらくしてから再度お試しください。",
        ],
        "highlight": "要約の生成に失敗しました。",
    }


# ============================================================
# 複数記事の一括処理
# ============================================================

def summarize_articles(articles: list[dict]) -> list[dict]:
    """
    記事リストを一括で要約・翻訳する。
    処理済みの要約フィールドを各記事辞書に追加して返す。
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY が設定されていません。\n"
            "取得方法: https://aistudio.google.com/app/apikey"
        )

    client = genai.Client(api_key=api_key)
    print(f"\n🤖 要約処理開始 ({len(articles)} 件)...")

    for i, article in enumerate(articles, 1):
        label = "英語→日本語" if article.get("lang") == "en" else "日本語要約"
        print(f"  [{i}/{len(articles)}] {label}: {article['title'][:45]}...")

        result = summarize_article(
            title=article.get("title", ""),
            content=article.get("content", ""),
            url=article.get("url", ""),
            lang=article.get("lang", "ja"),
            client=client,
        )
        article.update(result)

        # 無料枠: 1分15リクエスト制限への対策
        if i < len(articles):
            time.sleep(1)

    print("  ✅ 全記事の要約完了")
    return articles


# ============================================================
# 動作確認（そのまま実行できるサンプル）
# ============================================================

if __name__ == "__main__":
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        print("=" * 60)
        print("⚠️  GEMINI_API_KEY が未設定です")
        print("=" * 60)
        print()
        print("【無料APIキーの取得手順】")
        print("  1. https://aistudio.google.com/app/apikey を開く")
        print("  2. Googleアカウントでログイン")
        print("  3. 「APIキーを作成」をクリック")
        print("  4. 表示されたキー（AIza...）をコピー")
        print()
        print("【.env ファイルを作成して保存】")
        print("  ai-news-app/.env に以下を記載:")
        print("  GEMINI_API_KEY=AIzaxxxxxxxxxxxxxxxxxx")
        print()
        print("  ※ .env はGitHubに公開しないよう注意してください")
        exit(1)

    # サンプルデータ（日本語・英語 各1件）
    samples = [
        {
            "source": "Zenn",
            "title": "Claude 3.7のAIエージェント機能が凄すぎる件",
            "content": (
                "AnthropicがClaude 3.7を発表した。今回の目玉はAIエージェント機能で、"
                "複数のタスクを自律的にこなせるようになった。たとえばWebを検索しながら"
                "情報をまとめ、メールの下書きまで自動で行うことができる。"
                "さらに日本語対応も大幅に向上しており、自然なやりとりが可能になった。"
            ),
            "url": "https://zenn.dev/sample/articles/claude-37",
            "lang": "ja",
        },
        {
            "source": "Dev.to",
            "title": "OpenAI GPT-5 Is Here: What It Means for Everyday Users",
            "content": (
                "OpenAI has officially released GPT-5, its most powerful model yet. "
                "The model can understand images, audio, and text simultaneously. "
                "Users can now take a photo of a broken appliance and get repair instructions, "
                "or describe a symptom for detailed guidance. GPT-5 also remembers past "
                "conversations across sessions, making interactions feel more personal. "
                "Available via ChatGPT Plus and the API."
            ),
            "url": "https://dev.to/sample/gpt5",
            "lang": "en",
        },
    ]

    client = genai.Client(api_key=api_key)

    print("=" * 60)
    print("🧪 summarize.py 動作確認")
    print(f"   モデル: {MODEL}（無料枠）")
    print("=" * 60)

    for i, article in enumerate(samples, 1):
        label = "英語 → 日本語翻訳" if article["lang"] == "en" else "日本語要約"
        print(f"\n【サンプル {i}】{label}")
        print(f"  元タイトル : {article['title']}")
        print("  処理中...", end=" ", flush=True)

        result = summarize_article(
            title=article["title"],
            content=article["content"],
            url=article["url"],
            lang=article["lang"],
            client=client,
        )

        print("完了\n")
        print(f"  日本語タイトル : {result['title_ja']}")
        print(f"  要約:")
        for j, line in enumerate(result["summary"], 1):
            print(f"    {j}. {line}")
        print(f"  ✨ すごいポイント : {result['highlight']}")

        if i < len(samples):
            time.sleep(1)

    print("\n" + "=" * 60)
    print("✅ 動作確認完了")
    print("=" * 60)
