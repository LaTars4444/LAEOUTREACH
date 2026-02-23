import React, { useState, useEffect } from 'react';
import { useStore } from '../context/Store';
import { USA_STATES } from '../utils/constants';
import { Search, Loader2, MapPin, Activity, DollarSign } from 'lucide-react';

const Hunter: React.FC = () => {
  const { addLead, user } = useStore();
  const [selectedState, setSelectedState] = useState('');
  const [selectedCity, setSelectedCity] = useState('');
  const [isHunting, setIsHunting] = useState(false);
  const [queriesRun, setQueriesRun] = useState(0);
  const [progressLeads, setProgressLeads] = useState<any[]>([]);
  const [linkepyEnabled, setLinkepyEnabled] = useState(true);
  const [notifications, setNotifications] = useState<string[]>([]);

  useEffect(() => {
    if (!user?.hasAiAccess) console.warn("⛔ Access denied: AI module required.");
  }, [user]);

  const addNotification = (msg: string) => {
    setNotifications(prev => [msg, ...prev].slice(0, 50)); // Keep last 50
  };

  const handleHunt = async () => {
    if (!selectedState || !selectedCity) return;
    setIsHunting(true);
    setProgressLeads([]);
    addNotification(`🚀 Starting hunt in ${selectedCity}, ${selectedState}`);

    try {
      const response = await fetch('/api/start-hunt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state: selectedState, city: selectedCity, linkepyEnabled })
      });
      const data = await response.json();

      if (data.leads?.length) {
        for (const lead of data.leads) {
          addLead(lead);
          setProgressLeads(prev => [lead, ...prev]);
          addNotification(`✅ Lead added: ${lead.address} | ${lead.name}`);
          await new Promise(r => setTimeout(r, 200));
        }
      }

      addNotification(`🏁 Hunt complete: ${data.leadsAdded} leads harvested.`);
      setQueriesRun(prev => prev + 1);
    } catch (err: any) {
      addNotification(`❌ Hunt failed: ${err.message || 'Unknown error'}`);
    } finally {
      setIsHunting(false);
    }
  };

  const freeQueries = 100;
  const costPer1k = 5.0;
  const estimatedCost = queriesRun > freeQueries
    ? ((queriesRun - freeQueries) / 1000) * costPer1k
    : 0;

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div className="bg-slate-800 border border-slate-700 rounded-lg p-8 shadow-xl">

        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Search className="text-emerald-500" size={24} />
            <h2 className="text-2xl font-bold text-white">Lead Hunter V12 (ATTOM)</h2>
          </div>
          <div className="flex items-center gap-4">
            <div className="bg-slate-900 px-4 py-2 rounded-lg border border-slate-700 flex items-center gap-4">
              <div className="text-[10px] text-slate-500 uppercase font-bold flex items-center gap-1">
                <Activity size={10} /> Queries Today
              </div>
              <div className="text-white font-mono font-bold">{queriesRun} / {freeQueries}</div>
              <div className="text-[10px] text-slate-500 uppercase font-bold flex items-center gap-1">
                <DollarSign size={10} /> Est. Cost
              </div>
              <div className={`font-mono font-bold ${estimatedCost>0?'text-amber-400':'text-emerald-400'}`}>${estimatedCost.toFixed(2)}</div>
            </div>
          </div>
        </div>

        {/* State / City */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          <select className="w-full bg-slate-900 border border-slate-700 rounded-md px-4 py-3 text-white outline-none"
                  value={selectedState} onChange={e => { setSelectedState(e.target.value); setSelectedCity(''); }}
                  disabled={isHunting}>
            <option value="">Select State...</option>
            {Object.keys(USA_STATES).sort().map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <select className="w-full bg-slate-900 border border-slate-700 rounded-md px-4 py-3 text-white outline-none"
                  value={selectedCity} onChange={e => setSelectedCity(e.target.value)}
                  disabled={!selectedState || isHunting}>
            <option value="">Select City...</option>
            {selectedState && USA_STATES[selectedState].map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        {/* Linkepy toggle */}
        <div className="mb-4 flex items-center gap-2">
          <input type="checkbox" checked={linkepyEnabled} onChange={e => setLinkepyEnabled(e.target.checked)} />
          <span className="text-slate-300 text-sm">Enable Linkepy Enrichment</span>
        </div>

        {/* Hunt button */}
        <button onClick={handleHunt} disabled={isHunting || !selectedCity}
                className="w-full py-4 bg-emerald-600 hover:bg-emerald-500 text-white rounded-md flex items-center justify-center gap-3">
          {isHunting ? <><Loader2 className="animate-spin"/> HARVESTING LEADS...</> : <><MapPin /> START HUNT</>}
        </button>

        {/* Live progress feed */}
        <div className="mt-6 bg-slate-900 border border-slate-700 rounded p-4 max-h-80 overflow-y-auto">
          <h3 className="text-sm text-slate-400 font-mono uppercase mb-2">Live Progress</h3>
          {progressLeads.length === 0 && <p className="text-slate-500 text-xs">No leads harvested yet.</p>}
          <ul className="text-white text-sm space-y-1">
            {progressLeads.map(l => <li key={l.id}>{l.address} | {l.name} | {l.email||'No Email'} | {l.phone||'No Phone'}</li>)}
          </ul>
        </div>

        {/* Notifications panel */}
        <div className="mt-4 bg-slate-800 border border-slate-700 rounded p-4 max-h-60 overflow-y-auto">
          <h3 className="text-sm text-slate-400 font-mono uppercase mb-2">Notifications</h3>
          <ul className="text-slate-200 text-sm space-y-1">
            {notifications.map((note, idx) => <li key={idx}>{note}</li>)}
          </ul>
        </div>

      </div>
    </div>
  );
};

export default Hunter;
