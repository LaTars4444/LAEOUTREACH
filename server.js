import express from 'express';
import cors from 'cors';
import fs from 'fs';
import path from 'path';
import startHunt from './api/start-hunt.js';

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

// Render temp disk path
const DATA_PATH = path.join('/tmp', 'leads.json');
if (!fs.existsSync(DATA_PATH)) fs.writeFileSync(DATA_PATH, JSON.stringify([]));

// API endpoint
app.post('/api/start-hunt', async (req, res) => {
  try {
    await startHunt(req, res);
    const currentData = JSON.parse(fs.readFileSync(DATA_PATH, 'utf-8'));
    const newLeads = (res.leads || []).map(l => ({ ...l }));
    fs.writeFileSync(DATA_PATH, JSON.stringify([...currentData, ...newLeads], null, 2));
  } catch (err) {
    res.status(500).json({ error: err.message || 'Server error' });
  }
});

// Serve frontend build
app.use(express.static(path.join(process.cwd(), 'dist')));
app.get('*', (req, res) => {
  res.sendFile(path.join(process.cwd(), 'dist', 'index.html'));
});

app.listen(PORT, () => console.log(`🚀 Server running on port ${PORT}`));
