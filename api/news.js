export default async function handler(req, res) {
  const API_KEY = process.env.NEWS_API_KEY;

  try {
    const response = await fetch(
      `https://newsapi.org/v2/top-headlines?country=jp&pageSize=10&apiKey=${API_KEY}`
    );

    const data = await response.json();

    // 👇ここで整形
    const formatted = data.articles.map((a) => ({
      title: a.title,
      summary: [
        a.description || "概要なし",
        "最新ニュース",
        new Date(a.publishedAt).toLocaleString()
      ],
      image: a.urlToImage
    }));

    res.status(200).json({ articles: formatted });
  } catch (error) {
    res.status(500).json({ error: "Failed to fetch news" });
  }
}
