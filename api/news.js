import fs from 'fs';
import path from 'path';

export default function handler(req, res) {
  try {
    const filePath = path.join(process.cwd(), 'data', 'articles.json');
    const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    res.status(200).json(data);
  } catch (error) {
    res.status(500).json({ error: 'Failed to load articles' });
  }
}
