import React, { useState, useEffect } from 'react';
import { useStore } from '../context/Store';
import { USA_STATES } from '../utils/constants';
import { Search, Loader2, MapPin, AlertTriangle, Lock, CheckCircle2, DollarSign, Activity, Wifi } from 'lucide-react';
import Terminal from '../components/Terminal';
import { useNavigate } from 'react-router-dom';

const Hunter: React.FC = () => {
  const { addLog, addLead, user } = useStore();
  const navigate = useNavigate();
  const [selectedState, setSelectedState] = useState<string>('');
  const [selectedCity, setSelectedCity] = useState<string>('');
  const [isHunting, setIsHunting] = useState(false);
  const [queriesRun, setQueriesRun] = useState(0);

  // Paywall Check
  useEffect(() => {
    if (user && !user.hasAiAccess) {
      addLog("⛔ ACCESS DENIED: AI & Lead Hunter module required.", "error");
      navigate('/paywall');
    }
  }, [user, navigate, addLog]);

  if (!user?.hasAiAccess) return null;

  const handleTestConnection = async () => {
    const apiKey = process.env.GOOGLE_SEARCH_API_KEY;
    const cx = process.env.GOOGLE_SEARCH_CX;
    
    addLog("📡 TESTING CONNECTION...", "info");
    addLog(`🔑 KEY: ${apiKey ? 'Detected' : 'Missing'} | CX: ${cx ? 'Detected' : 'Missing'}`, 'info');

    if (!apiKey || !cx) return;

    try {
      const url = `https://www.googleapis.com/customsearch/v1?key=${apiKey}&cx=${cx}&q=test`;
      const response = await fetch(url);
      const data = await response.json();

      if (data.error) {
        addLog(`❌ TEST FAILED: ${data.error.message}`, "error");
        if (data.error.message.includes("access")) {
           addLog("👉 CHECK 1: Is 'Custom Search API' enabled in Cloud Console?", "warning");
           addLog("👉 CHECK 2: Does the API Key have 'Application Restrictions'? If set to 'IP addresses', it will FAIL in the browser. Set to 'None' or 'HTTP Referrers'.", "warning");
        }
      } else {
        addLog("✅ CONNECTION SUCCESSFUL: API is responding correctly.", "success");
      }
    } catch (e: any) {
      addLog(`❌ NETWORK ERROR: ${e.message}`, "error");
    }
  };

  const handleHunt = async () => {
    if (!selectedState || !selectedCity) return;

    setIsHunting(true);
    addLog(`🚀 MISSION STARTED: Lead Extraction in ${selectedCity}, ${selectedState}`, 'info');

    const apiKey = process.env.GOOGLE_SEARCH_API_KEY;
    const cx = process.env.GOOGLE_SEARCH_CX;

    if (!apiKey || !cx) {
      addLog("❌ CONFIG ERROR: Google Search API Key or CX ID missing in Environment Variables.", "error");
      setIsHunting(false);
      return;
    }

    const queries = [
      `site:zillow.com "for sale by owner" ${selectedCity} ${selectedState}`,
      `site:craigslist.org "fixer upper" ${selectedCity} ${selectedState}`,
      `"motivated seller" ${selectedCity} ${selectedState} real estate`
    ];

    let totalFound = 0;

    try {
      for (const query of queries) {
        addLog(`🔎 SCANNING: ${query}`, 'info');
        setQueriesRun(prev => prev + 1);
        
        const url = `https://www.googleapis.com/customsearch/v1?key=${apiKey}&cx=${cx}&q=${encodeURIComponent(query)}`;
        const response = await fetch(url);
        const data = await response.json();

        if (data.error) {
          throw new Error(data.error.message);
        }

        if (data.items && data.items.length > 0) {
          for (const item of data.items) {
            const snippet = (item.snippet || "") + " " + (item.title || "");
            const phoneMatch = snippet.match(/\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}/);
            const emailMatch = snippet.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);

            const newLead = {
              id: Date.now() + Math.random(),
              address: item.title || "Unknown Address",
              name: "Property Owner",
              phone: phoneMatch ? phoneMatch[0] : "None",
              email: emailMatch ? emailMatch[0] : "None",
              status: 'New' as const,
              source: 'Google Search API',
              emailedCount: 0,
              createdAt: new Date().toISOString(),
              arvEstimate: 0,
              repairEstimate: 0
            };

            addLead(newLead);
            totalFound++;
            addLog(`✅ HARVESTED: ${newLead.address.substring(0, 40)}...`, 'success');
            await new Promise(r => setTimeout(r, 1500));
          }
        } else {
          addLog(`⚠️ No results found for query segment.`, 'warning');
        }
      }
      
      addLog(`🏁 MISSION COMPLETE: Indexed ${totalFound} leads.`, 'info');

    } catch (error: any) {
      addLog(`❌ API ERROR: ${error.message}`, 'error');
    } finally {
      setIsHunting(false);
    }
  };

  // Cost Calculation
  const freeQueries = 100;
  const costPer1k = 5.00;
  const estimatedCost = queriesRun > freeQueries 
    ? ((queriesRun - freeQueries) / 1000) * costPer1k 
    : 0;

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div className="bg-slate-800 border border-slate-700 rounded-lg p-8 shadow-xl">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-emerald-500/10 rounded-lg border border-emerald-500/20">
              <Search className="text-emerald-500" size={24} />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-white">Lead Hunter V12</h2>
              <p className="text-slate-400">Live Google Search API Integration</p>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <button 
              onClick={handleTestConnection}
              className="text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 px-3 py-2 rounded border border-slate-600 flex items-center gap-2 transition-colors"
            >
              <Wifi size={12} /> Test Connection
            </button>

            <div className="bg-slate-900 px-4 py-2 rounded-lg border border-slate-700 flex items-center gap-4">
              <div>
                <div className="text-[10px] text-slate-500 uppercase font-bold flex items-center gap-1">
                  <Activity size={10} /> Queries Today
                </div>
                <div className="text-white font-mono font-bold">{queriesRun} / 100 (Free)</div>
              </div>
              <div className="h-8 w-px bg-slate-700"></div>
              <div>
                <div className="text-[10px] text-slate-500 uppercase font-bold flex items-center gap-1">
                  <DollarSign size={10} /> Est. Cost
                </div>
                <div className={`font-mono font-bold ${estimatedCost > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
                  ${estimatedCost.toFixed(2)}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Target State</label>
            <select 
              className="w-full bg-slate-900 border border-slate-700 rounded-md px-4 py-3 text-white focus:ring-2 focus:ring-emerald-500 focus:border-transparent outline-none"
              value={selectedState}
              onChange={(e) => {
                setSelectedState(e.target.value);
                setSelectedCity('');
              }}
              disabled={isHunting}
            >
              <option value="">Select Jurisdiction...</option>
              {Object.keys(USA_STATES).sort().map(state => (
                <option key={state} value={state}>{state}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Target City</label>
            <select 
              className="w-full bg-slate-900 border border-slate-700 rounded-md px-4 py-3 text-white focus:ring-2 focus:ring-emerald-500 focus:border-transparent outline-none"
              value={selectedCity}
              onChange={(e) => setSelectedCity(e.target.value)}
              disabled={!selectedState || isHunting}
            >
              <option value="">Select Metro Area...</option>
              {selectedState && USA_STATES[selectedState].map(city => (
                <option key={city} value={city}>{city}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="bg-slate-900/50 border border-slate-700 rounded-md p-4 mb-8 flex items-start gap-3">
          <CheckCircle2 className="text-emerald-500 shrink-0 mt-0.5" size={18} />
          <div className="text-sm text-slate-400">
            <strong className="text-slate-200 block mb-1">Live API Connection Ready</strong>
            This tool will use your configured Google Search API Key to perform real-time queries. 
            Results depend on your Custom Search Engine (CX) configuration.
          </div>
        </div>

        <button
          onClick={handleHunt}
          disabled={isHunting || !selectedCity}
          className={`w-full py-4 rounded-md font-bold text-lg tracking-wide transition-all flex items-center justify-center gap-3
            ${isHunting 
              ? 'bg-slate-700 text-slate-400 cursor-not-allowed' 
              : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg hover:shadow-emerald-500/20'
            }`}
        >
          {isHunting ? (
            <>
              <Loader2 className="animate-spin" />
              SCANNING WEB...
            </>
          ) : (
            <>
              <MapPin />
              INITIATE HUNT
            </>
          )}
        </button>
      </div>

      <div className="space-y-2">
        <h3 className="text-sm font-mono text-slate-500 uppercase tracking-wider">Live Operation Logs</h3>
        <Terminal />
      </div>
    </div>
  );
};

export default Hunter;
