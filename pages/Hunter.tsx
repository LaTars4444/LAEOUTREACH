import React, { useState } from 'react';
import { useStore } from '../context/Store';
import { USA_STATES } from '../utils/constants';
import { Loader2, MapPin, CheckCircle2, Settings, Globe } from 'lucide-react';

const Hunter: React.FC = () => {
  const { addLead } = useStore();
  const [selectedState, setSelectedState] = useState('');
  const [selectedCity, setSelectedCity] = useState('');
  const [isHunting, setIsHunting] = useState(false);
  const [progress, setProgress] = useState('');
  const [linkepyEnabled, setLinkepyEnabled] = useState(false);

  const handleHunt = async () => {
    if (!selectedState || !selectedCity) return;
    setIsHunting(true);
    setProgress('Starting hunt...');

    try {
      const response = await fetch('/api/start-hunt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state: selectedState, city: selectedCity, linkepyEnabled })
      });

      const data = await response.json();

      if (data.leads?.length > 0) {
        data.leads.forEach((lead: any) => addLead(lead));
        setProgress(`✅ Hunt complete: ${data.leads.length} leads added`);
      } else {
        setProgress('⚠️ No leads found');
      }
    } catch (err: any) {
      setProgress(`❌ Hunt failed: ${err.message}`);
    } finally {
      setIsHunting(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h2 className="text-2xl font-bold text-white flex items-center gap-2"><MapPin /> Lead Hunter</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="text-sm text-slate-300">State</label>
          <select
            value={selectedState}
            onChange={e => { setSelectedState(e.target.value); setSelectedCity(''); }}
            className="w-full p-3 rounded bg-slate-900 text-white"
          >
            <option value="">Select State</option>
            {Object.keys(USA_STATES).sort().map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <label className="text-sm text-slate-300">City</label>
          <select
            value={selectedCity}
            onChange={e => setSelectedCity(e.target.value)}
            className="w-full p-3 rounded bg-slate-900 text-white"
            disabled={!selectedState}
          >
            <option value="">Select City</option>
            {selectedState && USA_STATES[selectedState].map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <input type="checkbox" checked={linkepyEnabled} onChange={e => setLinkepyEnabled(e.target.checked)} id="linkepy" />
        <label htmlFor="linkepy" className="text-sm text-slate-400 flex items-center gap-1"><Globe size={12} /> Enrich with Linkepy</label>
      </div>

      <button
        onClick={handleHunt}
        disabled={isHunting || !selectedCity}
        className={`w-full py-4 rounded font-bold text-lg flex items-center justify-center gap-2 ${
          isHunting ? 'bg-slate-700 text-slate-400 cursor-not-allowed' : 'bg-emerald-600 hover:bg-emerald-500 text-white'
        }`}
      >
        {isHunting ? <><Loader2 className="animate-spin" /> Scanning...</> : <><MapPin /> Start Hunt</>}
      </button>

      <div className="p-4 bg-slate-900 rounded text-slate-200 font-mono">{progress}</div>
    </div>
  );
};

export default Hunter;
