import { useEffect, useState } from 'react';
import './App.css';
import jobData from './MASTER_ANALYSIS.json';

function App() {
  const [jobLink, setJobLink] = useState(""); // link from clearance jobs for webscraping
  const [selectModel, setSelectModel] = useState(""); //model chosen for analysis
  const [models, setModels] = useState([]); // LLM models
  const [search, setSearch] = useState(""); // search filter of the jobs returned
  const [loading,setLoading] = useState(false); // loading boolean to deactivate buttons during processing
  const [sortBy, setSortBy] = useState("score"); // Default sort by score
  const [resumes, setResumes] = useState([]); // resumes stored locally through UI
  const [selectedResume, setSelectedResume] = useState(""); // resume chosen by user

  const triggerScrapper = async() => {
    setLoading(true);
    try{
      const response = await fetch('http://localhost:8000/run-scraper',{
        method: 'POST',
      })
      const data = await response.json();
      alert(data.message);
      // Force page reload to show new data?
      window.location.reload();
    }catch (error){
      console.error("Error calling scrapper", error);
    } finally{
      setLoading(false);
    }
    }
  
  // fetch resumes on load
  const fetchResumes = () => {
    fetch('http://localhost:8000/get-resumes')
      .then(res => res.json())
      .then(data => {
        setResumes(data.resumes);
        if (data.resumes.length > 0) setSelectedResume(data.resumes[0]);
      });
  };
  useEffect(() => {
    fetchResumes();
  }, []);

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('resume', file);

    const res = await fetch('http://localhost:8000/upload-resume', {
      method: 'POST',
      body: formData
    });
    
    if (res.ok) {
      alert("Resume uploaded!");
      fetchResumes(); // Refresh the dropdown list
    }
  };

  // fetch Gemini LLM models
  useEffect(() => {
    fetch('http://localhost:8000/get-Models')
      .then(res => {
        if (!res.ok) throw new Error("Network response was not ok");
        return res.json();
      })
      .then(data => {
        if (data.models && data.models.length > 0) {
          setModels(data.models);
          // Store only the 'name' string for the backend, 
          // or the whole object if you need the display_name later.
          setSelectModel(data.models[0].name); 
        }
      })
      .catch(err => console.error("Error fetching models:", err));
  }, []);

  const handleScan = async () => {
    if (!selectedResume || !jobLink) {
      alert("Please select a resume and paste a job link.");
      return;
    }

    setLoading(true);
    const formData = new FormData();
    
    // These keys MUST match the request.form.get() keys in Python exactly
    formData.append('resume_name', selectedResume); 
    formData.append('link', jobLink);
    formData.append('model', selectModel);

    try {
      const response = await fetch('http://localhost:8000/run-scraper', {
        method: 'POST',
        body: formData, // Do NOT set Content-Type header; browser does it for FormData
      });

      if (!response.ok) {
        // Try to get the error message from the backend
        const errorData = await response.json();
        throw new Error(errorData.error || "Server Error");
      }

      const data = await response.json();
      alert(data.message);
      window.location.reload(); 

    } catch (err) {
      alert("Scan failed: " + err.message);
      console.error("Scan error details:", err);
    } finally {
      setLoading(false);
    }
  };


  // 1. Flatten the data
  const allJobs = Object.values(jobData).flat();

  // 2. Filter and then Sort
  const processedJobs = allJobs
    .filter(job => 
      job.role_name.toLowerCase().includes(search.toLowerCase()) ||
      job.company.toLowerCase().includes(search.toLowerCase())
    )
    .sort((a, b) => {
      if (sortBy === "score") {
        return b.score - a.score; // High to low
      } else if (sortBy === "company") {
        return a.company.localeCompare(b.company); // A to Z
      } else if (sortBy === "location") {
        return a.location.localeCompare(b.location); // A to Z
      } 
      // else if (sortBy === "salary"){
      // return a.salary.localeCompare(b.salary);
      // }
      return 0;
    });
// UI of page is below this line // UI of page is below this line// UI of page is below this line// UI of page is below this line
  return (
    <div className="dashboard">
      <header>
        <h1>Defense Careers Dashboard</h1>

        <div className="control-panel">
          {/* --- NEW: Resume Management Section --- */}
          <div className="resume-management">
            <div className="input-group">
              <label>1. Upload New Resume:</label>
              <input 
                type="file" 
                accept=".pdf,.docx,.txt" 
                onChange={handleFileUpload} 
                className="file-upload-input"
              />
            </div>

            <div className="input-group">
              <label htmlFor="resume-select">2. Select Active Resume:</label>
              <select 
                id="resume-select"
                value={selectedResume} 
                onChange={(e) => setSelectedResume(e.target.value)}
              >
                {resumes.length === 0 && <option>No resumes found...</option>}
                {resumes.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
              <button className="refresh-btn" onClick={fetchResumes} title="Refresh List">🔄</button>
            </div>
          </div>

          <hr className="panel-divider" />

          {/* --- Job Analysis Section --- */}
          <div className="input-group">
            <label>3. Analyze New Job:</label>
            <input
              type="text"
              placeholder="Paste the link from the search retrieved from ClearanceJobs"
              value={jobLink}
              onChange={(e) => setJobLink(e.target.value)}
            />
            
            <div className="model-selector">
              <label htmlFor="model-select">Choose AI Model:</label>
              <select 
                id="model-select"
                value={selectModel} 
                onChange={(e) => setSelectModel(e.target.value)}
              >
                {models.map((m) => (
                  <option key={m.name} value={m.name}>
                    {m.display_name} - ({m.tier})
                  </option>
                ))}
              </select>
            </div>

            <button className="analyze-btn" onClick={handleScan} disabled={loading || !selectedResume}>
              {loading ? "Analyzing..." : "Analyze Job"}
            </button>
          </div>
        </div>

        {/* Search and Sort Controls */}
        <div className="controls">
          <input 
            type="text" 
            placeholder="Search roles or companies..." 
            value={search}
            className="search-input"
            onChange={(e) => setSearch(e.target.value)}
          />

          <div className="sort-group">
            <label>Sort By: </label>
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
              <option value="score">Highest Match</option>
              <option value="company">Company (A-Z)</option>
              <option value="location">Location (A-Z)</option>
            </select>
          </div>
        </div>
      </header>

      <main className="job-list">
        {processedJobs.map((job, index) => (
          <div key={index} className="job-card">
            <div className="card-top">
              <span className="company-tag">{job.company}</span>
              <span className="score-badge">Fit: {job.score}%</span>
            </div>
            <h2>{job.role_name}</h2>
            <p className="location">📍 {job.location}</p>
            <p className="reason">{job.fit_reason}</p>
            
            <div className="skills">
              <strong>Gaps to bridge:</strong>
              <ul>
                {job.missing_skills.map((skill, i) => <li key={i}>{skill}</li>)}
              </ul>
            </div>
            <a href={job.link} target="_blank" rel="noreferrer" className="apply-btn">View Listing</a>
          </div>
        ))}
      </main>
    </div>
  );
}

export default App;

// https://www.clearancejobs.com/jobs?loc=5,9&received=31&ind=nq,nr,pg,nu,nv,nz,pd,nw,nt&limit=50