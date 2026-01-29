
import React, { useState, useEffect } from 'react';
import { useStore } from '../context/Store';
import { USA_STATES, STREET_NAMES, STREET_TYPES } from '../utils/constants';
import { Search, Loader2, MapPin, AlertTriangle, Lock, Database, Zap, Clipboard, Plus } from 'lucide-react';
import Terminal from '../components/Terminal';
import { useNavigate } from 'react-router-dom';
import { Lead } from '../types';

const Hunter: React.FC = () => {
  const { addLog, addLead, addLeads, user } = useStore();
  const navigate = useNavigate();
  
  // Tabs: 'manual' (User does heavy lifting) | 'auto' (Google/Synthetic)
  const [activeTab, setActiveTab] = useState<'manual' | 'auto'>('manual');

  // Manual Scout State
  const [rawText, setRawText] = useState('');
  const [parsedLead, setParsedLead] = useState<Partial<Lead>>({});
  const [isParsing, setIsParsing] = useState(false);

  // Auto Hunter State
  const [selectedState, setSelectedState] = useState<string>('');
  const [selectedCity, setSelectedCity] = useState<string>('');
  const [isHunting, setIsHunting] = useState(false);
  const [mode, setMode] = useState<'google' | 'synthetic'>('synthetic');

  // Paywall Check
  useEffect(() => {
    if (user && !user.hasAiAccess) {
      addLog("⛔ ACCESS DENIED: AI & Lead Hunter module required.", "error");
      navigate('/paywall');
    }
  }, [user, navigate, addLog]);

  if (!user?.hasAiAccess) return null;

  // --- MANUAL SCOUT LOGIC ---

  const parseRawText = async () => {
    if (!rawText.trim()) return;
    setIsParsing(true);
    addLog("👀 ANALYZING CLIPBOARD DATA...", "info");

    // 1. Try AI Parsing first (if Key exists)
    let apiKey = user?.groqApiKey;
    try { if (!apiKey) apiKey = process.env.GROQ_API_KEY; } catch(e) {}

    if (apiKey) {
      try {
        const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({
            messages: [
              { role: "system", content: "Extract real estate lead data from the user's text. Return ONLY a JSON object with keys: address, name, email, phone, askingPrice (number), propertyType. If missing, use null." },
              { role: "user", content: rawText }
            ],
            model: "llama3-70b-8192",
            temperature: 0.1
          })
        });
        const data = await response.json();
        const jsonStr = data.choices[0]?.message?.content;
        // Attempt to find JSON in response
        const jsonMatch = jsonStr.match(/\{[\s\S]*\}/);
        if (jsonMatch) {
          const extracted = JSON.parse(jsonMatch[0]);
          setParsedLead({
            address: extracted.address || "Unknown Address",
            name: extracted.name || "Property Owner",
            email: extracted.email || "",
            phone: extracted.phone || "",
            askingPrice: extracted.askingPrice || 0,
            propertyType: extracted.propertyType || "Single Family"
          });
          addLog("✅ AI PARSE COMPLETE: Data extracted successfully.", "success");
          setIsParsing(false);
          return;
        }
      } catch (e) {
        addLog("⚠️ AI PARSE FAILED, FALLING BACK TO REGEX...", "warning");
      }
    }

    // 2. Regex Fallback (Robust)
    setTimeout(() => {
      const emailMatch = rawText.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);
      const phoneMatch = rawText.match(/(?:\+?1[-. ]?)?\(?([0-9]{3})\)?[-. ]?([0-9]{3})[-. ]?([0-9]{4})/);
      const priceMatch = rawText.match(/\$[0-9,]+/);
      
      // Simple address heuristic (looks for number then words)
      const addressMatch = rawText.match(/\d+\s[A-z]+\s[A-z]+(?:,\s[A-z]+)?/);

      setParsedLead({
        address: addressMatch ? addressMatch[0] : "Address Not Found",
        email: emailMatch ? emailMatch[0] : "",
        phone: phoneMatch ? phoneMatch[0] : "",
        askingPrice: priceMatch ? parseInt(priceMatch[0].replace(/[$,]/g, '')) : 0,
        name: "Property Owner" // Hard to regex names reliably
      });
      
      addLog("✅ REGEX PARSE COMPLETE.", "success");
      setIsParsing(false);
    }, 800);
  };

  const saveManualLead = () => {
    if (!parsedLead.address) return;
    
    const newLead: Lead = {
      id: Date.now(),
      address: parsedLead.address || "Unknown",
      name: parsedLead.name || "Property Owner",
      email: parsedLead.email || "None",
      phone: parsedLead.phone || "None",
      askingPrice: parsedLead.askingPrice,
      status: 'New',
      source: 'Manual Scout',
      emailedCount: 0,
      createdAt: new Date().toISOString(),
      arvEstimate: (parsedLead.askingPrice || 0) * 1.3, // Rough estimate
      repairEstimate: 0
    };

    addLead(newLead);
    addLog(`💾 LEAD SAVED: ${newLead.address}`, "success");
    setRawText('');
    setParsedLead({});
  };

  // --- AUTO HUNTER LOGIC (Existing) ---

  const generateSyntheticLead = (city: string, state: string): Lead => {
    const streetNum = Math.floor(Math.random() * 9000) + 100;
    const street = STREET_NAMES[Math.floor(Math.random() * STREET_NAMES.length)];
    const type = STREET_TYPES[Math.floor(Math.random() * STREET_TYPES.length)];
    
    return {
      id: Date.now() + Math.random(),
      address: `${streetNum} ${street} ${type}, ${city}, ${state}`,
      name: Math.random() > 0.5 ? "Property Owner" : ["Smith Family Trust", "LLC Holdings", "Estate of J. Doe"][Math.floor(Math.random() * 3)],
      phone: `(555) ${Math.floor(Math.random() * 899) + 100}-${Math.floor(Math.random() * 8999) + 1000}`,
      email: `owner${Math.floor(Math.random() * 1000)}@example.com`,
      status: 'New',
      source: 'Titan Synthetic Grid',
      emailedCount: 0,
      createdAt: new Date().toISOString(),
      arvEstimate: Math.floor(Math.random() * 500000) + 100000,
      repairEstimate: Math.floor(Math.random() * 50000) + 10000
    };
  };

  const handleAutoHunt = async () => {
    if (!selectedState || !selectedCity) return;
    setIsHunting(true);
    
    if (mode === 'google') {
      addLog(`🚀 GOOGLE API: Initializing live search in ${selectedCity}, ${selectedState}...`, 'info');
      
      let apiKey = user?.groqApiKey || ''; 
      let cx = '';
      try {
        if (!apiKey) apiKey = process.env.GOOGLE_SEARCH_API_KEY || '';
        cx = process.env.GOOGLE_SEARCH_CX || '';
      } catch (e) {}

      if (!apiKey || !cx) {
        addLog("❌ CONFIG ERROR: Missing Google API Key or CX ID.", "error");
        setIsHunting(false);
        return;
      }

      const keywords = ["motivated seller", "fixer upper", "cash buyers only"];
      let totalFound = 0;

      const fetchGoogle = async () => {
        for (const kw of keywords) {
          if (!isHunting) break;
          const query = `${selectedCity} ${selectedState} real estate ${kw}`;
          addLog(`🔍 QUERYING: "${query}"`, 'info');

          try {
            // Standard Endpoint
            let url = `https://www.googleapis.com/customsearch/v1?key=${apiKey}&cx=${cx}&q=${encodeURIComponent(query)}&num=10`;
            let response = await fetch(url);
            
            // Paid Endpoint Failover
            if (response.status === 403) {
               addLog("⚠️ 403 DETECTED: Switching to Paid Endpoint...", "warning");
               url = `https://customsearch.googleapis.com/customsearch/v1?key=${apiKey}&cx=${cx}&q=${encodeURIComponent(query)}&num=10`;
               response = await fetch(url);
            }

            const data = await response.json();

            if (!response.ok) {
              addLog(`⚠️ API ERROR: ${data.error?.message}`, 'error');
              continue;
            }

            if (data.items && data.items.length > 0) {
              const newLeads: Lead[] = data.items.map((item: any) => {
                const snippet = (item.snippet || "") + " " + (item.title || "");
                const phoneMatch = snippet.match(/\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}/);
                const emailMatch = snippet.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);

                return {
                  id: Date.now() + Math.random(),
                  address: item.title || "Unknown Address",
                  name: "Property Owner",
                  phone: phoneMatch ? phoneMatch[0] : "None",
                  email: emailMatch ? emailMatch[0] : "None",
                  status: 'New',
                  source: 'Google Search API',
                  link: item.link,
                  emailedCount: 0,
                  createdAt: new Date().toISOString(),
                  arvEstimate: 0,
                  repairEstimate: 0
                };
              });

              addLeads(newLeads);
              totalFound += newLeads.length;
              addLog(`✅ FOUND ${newLeads.length} results for "${kw}"`, 'success');
            }
            await new Promise(r => setTimeout(r, 1500));
          } catch (err: any) {
            addLog(`❌ NETWORK ERROR: ${err.message}`, 'error');
          }
        }
        setIsHunting(false);
        addLog(`🏁 GOOGLE SEARCH COMPLETE: ${totalFound} leads extracted.`, 'info');
      };
      fetchGoogle();
    } else {
      addLog(`⚡ TITAN SYNTHETIC GRID: High-velocity mining in ${selectedCity}, ${selectedState}...`, 'info');
      const TOTAL_TARGET = 1000;
      const BATCH_SIZE = 50;
      let generated = 0;
      const runBatch = () => {
        if (generated >= TOTAL_TARGET) {
          setIsHunting(false);
          addLog(`🏁 SYNTHETIC MINING COMPLETE: ${TOTAL_TARGET} leads extracted.`, 'success');
          return;
        }
        const batch: Lead[] = [];
        for (let i = 0; i < BATCH_SIZE; i++) {
          batch.push(generateSyntheticLead(selectedCity, selectedState));
        }
        addLeads(batch);
        generated += BATCH_SIZE;
        addLog(`⚡ BATCH PROCESSED: ${generated}/${TOTAL_TARGET} leads indexed...`, 'info');
        setTimeout(runBatch, 200);
      };
      runBatch();
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      
      {/* Header & Tabs */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-emerald-500/10 rounded-lg border border-emerald-500/20">
            <Search className="text-emerald-500" size={24} />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-white">Lead Hunter V12</h2>
            <p className="text-slate-400">Acquisition & Extraction Engine</p>
          </div>
        </div>
        
        <div className="flex bg-slate-900 p-1 rounded-lg border border-slate-700">
          <button
            onClick={() => setActiveTab('manual')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-all flex items-center gap-2 ${
              activeTab === 'manual' ? 'bg-emerald-600 text-white shadow-lg' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Clipboard size={16} /> Manual Scout
          </button>
          <button
            onClick={() => setActiveTab('auto')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-all flex items-center gap-2 ${
              activeTab === 'auto' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Database size={16} /> Auto-Hunter
          </button>
        </div>
      </div>

      {/* MANUAL SCOUT INTERFACE */}
      {activeTab === 'manual' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          
          {/* Input Zone */}
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6 shadow-xl flex flex-col h-full">
            <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
              <Clipboard className="text-emerald-400" /> Raw Data Input
            </h3>
            <p className="text-sm text-slate-400 mb-4">
              Paste listing details from Zillow, Redfin, Craigslist, or Facebook. The system will extract the data automatically.
            </p>
            <textarea
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
              placeholder="Paste listing text here..."
              className="flex-1 w-full bg-slate-900 border border-slate-700 rounded-lg p-4 text-slate-300 focus:border-emerald-500 outline-none font-mono text-sm resize-none min-h-[300px]"
            />
            <button
              onClick={parseRawText}
              disabled={isParsing || !rawText.trim()}
              className="mt-4 w-full bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-3 rounded-lg flex items-center justify-center gap-2 transition-all"
            >
              {isParsing ? <Loader2 className="animate-spin" /> : <Zap size={18} />}
              ANALYZE CLIPBOARD
            </button>
          </div>

          {/* Extraction Preview */}
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6 shadow-xl flex flex-col h-full">
            <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
              <Database className="text-blue-400" /> Extracted Data
            </h3>
            
            <div className="flex-1 space-y-4">
              <div className="bg-slate-900 p-4 rounded-lg border border-slate-700">
                <label className="text-xs text-slate-500 uppercase font-bold">Property Address</label>
                <div className="text-white font-medium text-lg truncate">{parsedLead.address || "---"}</div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-slate-900 p-4 rounded-lg border border-slate-700">
                  <label className="text-xs text-slate-500 uppercase font-bold">Asking Price</label>
                  <div className="text-emerald-400 font-mono text-lg">
                    {parsedLead.askingPrice ? `$${parsedLead.askingPrice.toLocaleString()}` : "---"}
                  </div>
                </div>
                <div className="bg-slate-900 p-4 rounded-lg border border-slate-700">
                  <label className="text-xs text-slate-500 uppercase font-bold">Est. ARV</label>
                  <div className="text-blue-400 font-mono text-lg">
                    {parsedLead.askingPrice ? `$${(parsedLead.askingPrice * 1.3).toLocaleString()}` : "---"}
                  </div>
                </div>
              </div>

              <div className="bg-slate-900 p-4 rounded-lg border border-slate-700">
                <label className="text-xs text-slate-500 uppercase font-bold">Contact Info</label>
                <div className="flex flex-col gap-1 mt-1">
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Email:</span>
                    <span className="text-white">{parsedLead.email || "Not Found"}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Phone:</span>
                    <span className="text-white">{parsedLead.phone || "Not Found"}</span>
                  </div>
                </div>
              </div>
            </div>

            <button
              onClick={saveManualLead}
              disabled={!parsedLead.address}
              className={`mt-6 w-full py-3 rounded-lg font-bold flex items-center justify-center gap-2 transition-all ${
                parsedLead.address 
                  ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg' 
                  : 'bg-slate-700 text-slate-500 cursor-not-allowed'
              }`}
            >
              <Plus size={18} /> ADD TO PIPELINE
            </button>
          </div>
        </div>
      )}

      {/* AUTO HUNTER INTERFACE */}
      {activeTab === 'auto' && (
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-8 shadow-xl">
          {/* Mode Selector */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
            <button
              onClick={() => setMode('synthetic')}
              className={`p-4 rounded-lg border flex items-center gap-3 transition-all ${
                mode === 'synthetic' 
                  ? 'bg-emerald-500/10 border-emerald-500 text-white' 
                  : 'bg-slate-900 border-slate-700 text-slate-400 hover:border-slate-600'
              }`}
            >
              <Zap size={24} className={mode === 'synthetic' ? 'text-emerald-500' : 'text-slate-500'} />
              <div className="text-left">
                <div className="font-bold">Titan Synthetic Grid</div>
                <div className="text-xs opacity-70">FREE • 1,000+ Leads • Instant</div>
              </div>
            </button>

            <button
              onClick={() => setMode('google')}
              className={`p-4 rounded-lg border flex items-center gap-3 transition-all ${
                mode === 'google' 
                  ? 'bg-blue-500/10 border-blue-500 text-white' 
                  : 'bg-slate-900 border-slate-700 text-slate-400 hover:border-slate-600'
              }`}
            >
              <Database size={24} className={mode === 'google' ? 'text-blue-500' : 'text-slate-500'} />
              <div className="text-left">
                <div className="font-bold">Google Search API</div>
                <div className="text-xs opacity-70">PAID • Real-time • Uses Credit</div>
              </div>
            </button>
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

          <button
            onClick={handleAutoHunt}
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
                {mode === 'synthetic' ? 'MINING SYNTHETIC GRID...' : 'EXTRACTING FROM GOOGLE...'}
              </>
            ) : (
              <>
                <MapPin />
                INITIATE HUNT
              </>
            )}
          </button>
        </div>
      )}

      <div className="space-y-2">
        <h3 className="text-sm font-mono text-slate-500 uppercase tracking-wider">Live Operation Logs</h3>
        <Terminal />
      </div>
    </div>
  );
};

export default Hunter;
