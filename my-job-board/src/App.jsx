import { useEffect, useState } from 'react';
import './App.css';
import jobData from './MASTER_ANALYSIS.json';

function App() {
  const [jobLink, setJobLink] = useSate("");
  const [selectModel, setSelectModel] = useState("");
  const [models, setModels] = useState([]);
  const [search, setSearch] = useState("");
  const [loading,setLoading] = useState(false);
  const [sortBy, setSortBy] = useState("score"); // Default sort by score

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
  

  // fetch Gemini LLM models
  useEffect(() =>{
    fetch('http://localhost:8000/get-models')
    .then(res => res.json())
    .then(data => {
      setModels(data.models);
      setSelectModel(data.models[0]) // set first model as the default
    })
    .catch(err => console.error("Error fetching models", err));
  }, []);

  const handleScan = async () => {
    if(!jobLink) return alert("Please past a job link first.");
    setLoading(true);
    try{
      const response = await fetch('http://localhost:8000/run-scraper',{
        method: 'POST',
        headers: {},
        body: JSON.stringify({
          link:jobLink,
          model: selectModel
        })
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
      return 0;
    });

  return (
    <div className="dashboard">
      <header>
        <h1>Defense Careers Dashboard</h1>
        {/* { <button onClick = {triggerScrapper}
          disabled = {loading}
          className = 'run-btn'
        >
          {loading ? "Running Srapper..." : "Refresh Job Data"}
        </button> */} 
        
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