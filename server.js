import express from 'express';
import cors from 'cors';
import fs from 'fs';
import path from 'path';
import startHunt from './api/start-hunt.js'; // use .js if transpiled

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

// Use Render disk for data storage
const DATA_PATH = path.join('/tmp', 'leads.json');

// Ensure file exists
if (!fs.existsSync(DATA_PATH)) fs.writeFileSync(DATA_PATH, JSON.stringify([]));

// API route
app.post('/api/start-hunt', async (req, res) => {
  // Wrap startHunt to save leads
  const mockRes = {
    status: (code) => {
      return {
        json: (obj: any) => res.status(code).json(obj)
      };
    }
  };

  try {
    await startHunt(req, mockRes);

    // Append to disk
    const currentData = JSON.parse(fs.readFileSync(DATA_PATH, 'utf-8'));
    const newLeads = (mockRes.leads || []).map((l: any) => ({ ...l }));
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
