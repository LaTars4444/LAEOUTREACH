import React, { useState, useEffect } from 'react';
import { useStore } from '../context/Store';
import { USA_STATES } from '../utils/constants';
import { Search, Loader2, MapPin, AlertTriangle, Lock, CheckCircle2, DollarSign, Activity, Wifi, Settings } from 'lucide-react';
import Terminal from '../components/Terminal';
import { useNavigate, Link } from 'react-router-dom';

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

  // --- DYNAMIC QUERY GENERATOR ---
  const generateQueries = (city: string, state: string) => {
    const baseQueries = [];
    
    // 1. Always include FSBO
    baseQueries.push(`site:zillow.com "for sale by owner" ${city} ${state}`);
    baseQueries.push(`"for sale by owner" ${city} ${state} real estate`);

    // 2. Condition-based keywords
    if (user?.bbCondition === 'Distressed' || user?.bbStrategy === 'Fix and Flip') {
      baseQueries.push(`site:craigslist.org "fixer upper" ${city} ${state}`);
      baseQueries.push(`"needs work" ${city} ${state} house for sale`);
      baseQueries.push(`"TLC" ${city} ${state} real estate`);
      baseQueries.push(`"damage" ${city} ${state} house`);
    } else if (user?.bbCondition === 'Turnkey') {
      baseQueries.push(`"recently renovated" ${city} ${state}`);
      baseQueries.push(`"move in ready" ${city} ${state}`);
    }

    // 3. Strategy-based keywords
    if (user?.bbStrategy === 'Wholesale') {
      baseQueries.push(`"cash only" ${city} ${state} real estate`);
      baseQueries.push(`"investor special" ${city} ${state}`);
      baseQueries.push(`"must sell" ${city} ${state}`);
    } else if (user?.bbStrategy === 'Buy and Hold') {
      baseQueries.push(`"tenant in place" ${city} ${state}`);
      baseQueries.push(`"income property" ${city} ${state}`);
    }

    // 4. Asset Class keywords
    if (user?.bbPropertyType === 'Multi-Family') {
      baseQueries.push(`"duplex" ${city} ${state}`);
      baseQueries.push(`"triplex" ${city} ${state}`);
      baseQueries.push(`"fourplex" ${city} ${state}`);
    } else if (user?.bbPropertyType === 'Commercial') {
      baseQueries.push(`"commercial building" ${city} ${state} for sale`);
    } else if (user?.bbPropertyType === 'Land') {
      baseQueries.push(`"vacant land" ${city} ${state}`);
      baseQueries.push(`"lot for sale" ${city} ${state}`);
    }

    // Deduplicate and limit to 5 queries per run to save API quota
    return [...new Set(baseQueries)].slice(0, 5);
  };

  const handleTestConnection = async () => {
    const apiKey = process.env.GOOGLE_SEARCH_API_KEY;
    const cx = process.env.GOOGLE_SEARCH_CX;
    
    addLog("📡 TESTING CONNECTION...", "info");
    
    if (apiKey) {
      const start = apiKey.substring(0, 4);
      const end = apiKey.substring(apiKey.length - 4);
      addLog(`🔑 DEBUG: Using Key: ${start}...${end}`, 'info');
    } else {
      addLog("❌ DEBUG: No API Key found in Environment Variables.", "error");
    }

    if (!apiKey || !cx) return;

    try {
      const url = `https://www.googleapis.com/customsearch/v1?key=${apiKey}&cx=${cx}&q=test`;
      const response = await fetch(url);
      const data = await response.json();

      if (data.error) {
        addLog(`❌ TEST FAILED: ${data.error.message}`, "error");
        console.error("FULL GOOGLE ERROR:", data); // Log full object to browser console
        
        if (data.error.code === 403) {
           addLog("👉 403 ERROR: Usually means 'Custom Search API' is not enabled in Library OR Billing is inactive.", "warning");
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

    // Generate Dynamic Queries based on Buy Box
    const queries = generateQueries(selectedCity, selectedState);
    addLog(`📋 CONFIG: Generated ${queries.length} targeted queries based on Buy Box settings.`, 'info');

    let totalFound = 0;

    try {
      for (const query of queries) {
        addLog(`🔎 SCANNING: ${query}`, 'info');
        setQueriesRun(prev => prev + 1);
        
        const url = `https://www.googleapis.com/customsearch/v1?key=${apiKey}&cx=${cx}&q=${encodeURIComponent(query)}`;
        const response = await fetch(url);
        const data = await response.json();

        if (data.error) {
          // Detailed Error Logging
          addLog(`❌ API ERROR (${data.error.code}): ${data.error.message}`, 'error');
          
          if (data.error.details) {
             data.error.details.forEach((detail: any) => {
               addLog(`   ↳ Reason: ${detail.reason} - ${detail.domain}`, 'warning');
             });
          }
          
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
      // Error already logged above
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

        <div className="bg-slate-900/50 border border-slate-700 rounded-md p-4 mb-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="text-emerald-500 shrink-0 mt-0.5" size={18} />
            <div className="text-sm text-slate-400">
              <strong className="text-slate-200 block mb-1">Live API Connection Ready</strong>
              Queries are dynamically generated based on your <Link to="/buy-box" className="text-emerald-400 hover:underline">Buy Box Settings</Link>.
            </div>
          </div>
          <div className="text-xs text-slate-500 bg-slate-900 px-3 py-2 rounded border border-slate-700">
            <div className="font-bold text-slate-300 mb-1 flex items-center gap-1"><Settings size={10} /> Active Filters:</div>
            <div>Strategy: <span className="text-emerald-400">{user?.bbStrategy || 'Any'}</span></div>
            <div>Condition: <span className="text-emerald-400">{user?.bbCondition || 'Any'}</span></div>
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
