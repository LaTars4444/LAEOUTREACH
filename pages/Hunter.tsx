import React, { useState, useEffect } from 'react';
import { useStore } from '../context/Store';
import { USA_STATES } from '../utils/constants';
import { Search, Loader2, MapPin, Wifi, Key, ShieldAlert, Settings, ExternalLink, Globe, CheckCircle2, Activity, DollarSign } from 'lucide-react';
import Terminal from '../components/Terminal';
import { useNavigate, Link } from 'react-router-dom';

const Hunter: React.FC = () => {
  const { addLog, addLead, user } = useStore();
  const navigate = useNavigate();
  const [selectedState, setSelectedState] = useState<string>('');
  const [selectedCity, setSelectedCity] = useState<string>('');
  const [isHunting, setIsHunting] = useState(false);
  const [queriesRun, setQueriesRun] = useState(0);

  // --- LINKEPY TOGGLE ---
  const [linkepyEnabled, setLinkepyEnabled] = useState(true);

  // --- Live Progress ---
  const [progressLeads, setProgressLeads] = useState<any[]>([]);

  // Manual Override State
  const [manualKey, setManualKey] = useState('');
  const [manualCx, setManualCx] = useState('');
  const [showManual, setShowManual] = useState(false);
  const [forcePublic, setForcePublic] = useState(false);

  // Paywall Check
  useEffect(() => {
    if (user && !user.hasAiAccess) {
      addLog("⛔ ACCESS DENIED: AI & Lead Hunter module required.", "error");
      navigate('/paywall');
    }
  }, [user, navigate, addLog]);

  if (!user?.hasAiAccess) return null;

  // --- GENERIC QUERY GENERATOR (Optional, can be simplified) ---
  const generateQueries = (city: string, state: string) => {
    // For ATTOM, queries can just be the city/state placeholder
    return [`${city}, ${state}`];
  };

  // --- HANDLE HUNT ---
  const handleHunt = async () => {
    if (!selectedState || !selectedCity) return;

    setIsHunting(true);
    setProgressLeads([]);
    addLog(`🚀 MISSION STARTED: Lead Extraction in ${selectedCity}, ${selectedState}`, 'info');

    try {
      const queries = generateQueries(selectedCity, selectedState);
      let totalLeads = 0;

      for (const query of queries) {
        addLog(`🔎 FETCHING LEADS FOR: ${query}`, 'info');
        setQueriesRun(prev => prev + 1);

        // --- 1) ATTOM API Call ---
        const attomUrl = `https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/address?state=${selectedState}&city=${selectedCity}&pageSize=50`;
        const attomRes = await fetch(attomUrl, {
          headers: { 'apikey': process.env.ATTOM_API_KEY || '' }
        });
        const attomData = await attomRes.json();

        for (const prop of attomData.properties || []) {
          const ownerName = prop.owner?.name || "Property Owner";
          let email = null;
          let phone = null;

          // --- 2) Linkepy enrichment ---
          if (linkepyEnabled) {
            try {
              const enrichRes = await fetch('https://api.linkepy.com/api/enrichment/email-lookup', {
                method: 'POST',
                headers: {
                  'Authorization': `Bearer ${process.env.LINKEPY_API_KEY}`,
                  'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                  firstName: ownerName.split(' ')[0],
                  lastName: ownerName.split(' ')[1] || '',
                  location: `${selectedCity}, ${selectedState}`
                })
              });
              const enrichData = await enrichRes.json();
              email = enrichData?.email || null;
              phone = enrichData?.phone || null;
            } catch (err) {
              addLog(`⚠️ LINKEPY ENRICHMENT FAILED: ${err}`, 'warning');
            }
          }

          const newLead = {
            id: Date.now() + Math.random(),
            address: prop.address?.line1 || "Unknown Address",
            name: ownerName,
            email,
            phone,
            status: 'New',
            source: 'ATTOM',
            createdAt: new Date().toISOString(),
          };

          // Add to dashboard via your store
          addLead(newLead);

          // --- LIVE PROGRESS ---
          setProgressLeads(prev => [newLead, ...prev]);

          totalLeads++;
          addLog(`✅ HARVESTED: ${newLead.address.substring(0, 40)}...`, 'success');

          await new Promise(r => setTimeout(r, 500)); // small delay for progress UI
        }
      }

      addLog(`🏁 MISSION COMPLETE: Indexed ${totalLeads} leads.`, 'info');
    } catch (err: any) {
      console.error(err);
      addLog(`❌ HUNT ERROR: ${err.message || 'Unknown error'}`, 'error');
    } finally {
      setIsHunting(false);
    }
  };

  const freeQueries = 100;
  const costPer1k = 5.00;
  const estimatedCost = queriesRun > freeQueries 
    ? ((queriesRun - freeQueries) / 1000) * costPer1k 
    : 0;

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div className="bg-slate-800 border border-slate-700 rounded-lg p-8 shadow-xl">
        {/* --- Header --- */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-emerald-500/10 rounded-lg border border-emerald-500/20">
              <Search className="text-emerald-500" size={24} />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-white">Lead Hunter V12 (ATTOM)</h2>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="bg-slate-900 px-4 py-2 rounded-lg border border-slate-700 flex items-center gap-4">
              <div>
                <div className="text-[10px] text-slate-500 uppercase font-bold flex items-center gap-1">
                  <Activity size={10} /> Queries Today
                </div>
                <div className="text-white font-mono font-bold">{queriesRun} / {freeQueries} (Free)</div>
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

        {/* --- State / City selectors --- */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Target State</label>
            <select 
              className="w-full bg-slate-900 border border-slate-700 rounded-md px-4 py-3 text-white outline-none"
              value={selectedState}
              onChange={(e) => { setSelectedState(e.target.value); setSelectedCity(''); }}
              disabled={isHunting}
            >
              <option value="">Select State...</option>
              {Object.keys(USA_STATES).sort().map(state => (
                <option key={state} value={state}>{state}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Target City</label>
            <select 
              className="w-full bg-slate-900 border border-slate-700 rounded-md px-4 py-3 text-white outline-none"
              value={selectedCity}
              onChange={(e) => setSelectedCity(e.target.value)}
              disabled={!selectedState || isHunting}
            >
              <option value="">Select City...</option>
              {selectedState && USA_STATES[selectedState].map(city => (
                <option key={city} value={city}>{city}</option>
              ))}
            </select>
          </div>
        </div>

        {/* --- Linkepy Toggle --- */}
        <div className="mb-4 flex items-center gap-2">
          <input 
            type="checkbox"
            id="linkepyToggle"
            checked={linkepyEnabled}
            onChange={(e) => setLinkepyEnabled(e.target.checked)}
            className="h-5 w-5 cursor-pointer"
          />
          <label htmlFor="linkepyToggle" className="text-slate-300 text-sm">Enable Linkepy Enrichment</label>
        </div>

        {/* --- Hunt Button --- */}
        <button
          onClick={handleHunt}
          disabled={isHunting || !selectedCity}
          className={`w-full py-4 rounded-md font-bold text-lg tracking-wide transition-all flex items-center justify-center gap-3
            ${isHunting ? 'bg-slate-700 text-slate-400 cursor-not-allowed' : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg'}
          `}
        >
          {isHunting ? (
            <>
              <Loader2 className="animate-spin" />
              HARVESTING LEADS...
            </>
          ) : (
            <>
              <MapPin />
              START HUNT
            </>
          )}
        </button>

        {/* --- LIVE PROGRESS --- */}
        <div className="mt-6 bg-slate-900 border border-slate-700 rounded p-4 max-h-80 overflow-y-auto">
          <h3 className="text-sm text-slate-400 font-mono uppercase mb-2">Live Progress</h3>
          {progressLeads.length === 0 && <p className="text-slate-500 text-xs">No leads harvested yet.</p>}
          <ul className="text-white text-sm space-y-1">
            {progressLeads.map(lead => (
              <li key={lead.id}>
                {lead.address} | {lead.name} | {lead.email || 'No Email'} | {lead.phone || 'No Phone'}
              </li>
            ))}
          </ul>
        </div>

      </div>

      {/* --- Terminal Logs --- */}
      <div className="space-y-2">
        <h3 className="text-sm font-mono text-slate-500 uppercase tracking-wider">Live Operation Logs</h3>
        <Terminal />
      </div>
    </div>
  );
};

export default Hunter;
