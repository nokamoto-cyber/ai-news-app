export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');

  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    return res.status(500).json({ error: 'GITHUB_TOKEN が設定されていません' });
  }

  try {
    const response = await fetch(
      'https://api.github.com/repos/nokamoto-cyber/ai-news-app/actions/workflows/update.yml/dispatches',
      {
        method: 'POST',
        headers: {
          Authorization: `token ${token}`,
          Accept: 'application/vnd.github.v3+json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ref: 'main' }),
      }
    );

    if (response.status === 204) {
      return res.status(200).json({ status: 'ok', message: 'ワークフローを起動しました' });
    } else {
      const body = await response.text();
      return res.status(500).json({ error: `GitHub API エラー: ${response.status}`, detail: body });
    }
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
}
