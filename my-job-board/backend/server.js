// backend/server.js
const fs = require('fs');
const express = require('express');
const app = express();
app.use(express.json());

const TRACKER_FILE = './applied_jobs.json';

app.post('/api/apply', (req, res) => {
    const { jobId } = req.body;
    
    // Read existing file
    let appliedData = JSON.parse(fs.readFileSync(TRACKER_FILE, 'utf8') || "[]");
    
    if (!appliedData.includes(jobId)) {
        appliedData.push(jobId);
        fs.writeFileSync(TRACKER_FILE, JSON.stringify(appliedData, null, 2));
    }
    res.json({ success: true });
});

app.get('/api/applied', (req, res) => {
    const data = fs.readFileSync(TRACKER_FILE, 'utf8');
    res.send(data);
});