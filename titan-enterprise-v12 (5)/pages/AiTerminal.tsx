import React, { useState, useEffect, useRef } from 'react';
import { useStore } from '../context/Store';
import { Terminal, Send, Cpu, Lock, AlertCircle, CheckCircle2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const AiTerminal: React.FC = () => {
  const { user, addLog } = useStore();
  const navigate = useNavigate();
  const [input, setInput] = useState('');
  const [history, setHistory] = useState<{ role: 'user' | 'ai' | 'system'; content: string }[]>([
    { role: 'system', content: 'Titan Intelligence Module v12.0.0 initialized. Connected to Llama-3-70b-8192.' }
  ]);
  const [isThinking, setIsThinking] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Paywall Check
  useEffect(() => {
    if (user && !user.hasAiAccess) {
      addLog("⛔ ACCESS DENIED: AI module required.", "error");
      navigate('/paywall');
    }
  }, [user, navigate, addLog]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [history]);

  if (!user?.hasAiAccess) return null;

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMsg = input;
    setInput('');
    setHistory(prev => [...prev, { role: 'user', content: userMsg }]);
    setIsThinking(true);

    try {
      // PRIORITY: User Setting -> Render Env Var -> Empty
      // Note: In Vite/CRA, process.env.GROQ_API_KEY is replaced at build time.
      // We use a safe check to avoid runtime errors if process is undefined.
      let systemKey = '';
      try {
        systemKey = process.env.GROQ_API_KEY || '';
      } catch (e) {
        // Ignore if process is not defined
      }

      const apiKey = user.groqApiKey || systemKey;

      if (apiKey && apiKey.startsWith('gsk_')) {
        // REAL API CALL
        const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${apiKey}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            messages: [
              { role: "system", content: "You are Titan AI, an expert real estate investment assistant. You help with cold calling scripts, ARV calculations, and negotiation strategies. Keep answers concise and professional." },
              ...history.filter(h => h.role !== 'system').map(h => ({ role: h.role === 'ai' ? 'assistant' : 'user', content: h.content })),
              { role: "user", content: userMsg }
            ],
            model: "llama3-70b-8192",
            temperature: 0.7
          })
        });

        const data = await response.json();
        
        if (data.error) {
          throw new Error(data.error.message);
        }

        const aiResponse = data.choices[0]?.message?.content || "No response from satellite.";
        setHistory(prev => [...prev, { role: 'ai', content: aiResponse }]);

      } else {
        // SIMULATION MODE (No Key Provided)
        setTimeout(() => {
          let response = "⚠️ SIMULATION MODE: To enable live intelligence, please add your Groq API Key in Settings or Render Environment Variables.\n\n";
          
          if (userMsg.toLowerCase().includes('script')) {
            response += "Here is a high-converting cold email script:\n\nSubject: Cash offer for [[ADDRESS]]\n\nHi [[NAME]],\n\nI'm a local investor looking to buy a property in your neighborhood this week. I can pay all closing costs and buy 'as-is'.\n\nAre you open to a cash offer?\n\nBest,\n[Your Name]";
          } else if (userMsg.toLowerCase().includes('arv')) {
            response += "To calculate ARV (After Repair Value), look for 3-5 sold comparables within 0.5 miles from the last 6 months. Adjust for square footage and condition. A safe formula is: (Avg Price/SqFt of Comps) * Subject SqFt.";
          } else {
            response += "I can assist with:\n1. Cold Call Scripts\n2. ARV Calculations\n3. Negotiation Tactics\n\n(Add API Key for full conversation capabilities)";
          }

          setHistory(prev => [...prev, { role: 'ai', content: response }]);
        }, 1000);
      }
    } catch (error: any) {
      setHistory(prev => [...prev, { role: 'system', content: `Error: ${error.message}` }]);
    } finally {
      setIsThinking(false);
    }
  };

  // Check if key exists for UI status
  let hasKey = !!user.groqApiKey;
  try {
    if (process.env.GROQ_API_KEY) hasKey = true;
  } catch(e) {}

  return (
    <div className="max-w-4xl mx-auto h-[calc(100vh-8rem)] flex flex-col">
      <div className="bg-slate-800 border border-slate-700 rounded-t-lg p-4 flex items-center justify-between">
        <div className="flex items-center gap-2 text-purple-400">
          <Cpu size={20} />
          <h2 className="font-bold tracking-wider">GROQ INTELLIGENCE TERMINAL</h2>
        </div>
        <div className="flex items-center gap-4">
           {!hasKey ? (
             <div className="flex items-center gap-1 text-amber-400 text-xs">
               <AlertCircle size={12} />
               <span>SIMULATION MODE</span>
             </div>
           ) : (
             <div className="flex items-center gap-1 text-emerald-400 text-xs">
               <CheckCircle2 size={12} />
               <span>LIVE UPLINK ACTIVE</span>
             </div>
           )}
           <div className="text-xs text-slate-500 font-mono">
             STATUS: ONLINE
           </div>
        </div>
      </div>

      <div className="flex-1 bg-slate-950 border-x border-slate-700 p-6 overflow-y-auto font-mono text-sm space-y-6" ref={scrollRef}>
        {history.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] rounded-lg p-4 ${
              msg.role === 'user' 
                ? 'bg-slate-800 text-slate-200 border border-slate-700' 
                : msg.role === 'system'
                ? 'bg-slate-900 text-emerald-500 border border-emerald-900/30 text-xs'
                : 'bg-purple-900/20 text-purple-200 border border-purple-500/20'
            }`}>
              <div className="text-[10px] opacity-50 mb-1 uppercase">
                {msg.role === 'user' ? 'Operator' : msg.role === 'system' ? 'System' : 'Titan AI'}
              </div>
              <div className="whitespace-pre-wrap">{msg.content}</div>
            </div>
          </div>
        ))}
        {isThinking && (
          <div className="flex justify-start">
            <div className="bg-purple-900/20 text-purple-200 border border-purple-500/20 rounded-lg p-4 flex items-center gap-2">
              <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce"></div>
              <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce delay-75"></div>
              <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce delay-150"></div>
            </div>
          </div>
        )}
      </div>

      <form onSubmit={handleSend} className="bg-slate-800 border border-slate-700 rounded-b-lg p-4 flex gap-4">
        <div className="flex-1 relative">
          <Terminal className="absolute left-3 top-3.5 text-slate-500" size={18} />
          <input 
            type="text" 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={hasKey ? "Ask Titan AI anything..." : "Simulation Mode: Ask for 'scripts' or 'ARV'..."}
            className="w-full bg-slate-900 border border-slate-700 rounded-md py-3 pl-10 pr-4 text-white focus:border-purple-500 outline-none font-mono text-sm"
          />
        </div>
        <button 
          type="submit"
          disabled={isThinking || !input.trim()}
          className="bg-purple-600 hover:bg-purple-500 text-white px-6 rounded-md font-bold flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <Send size={18} />
          SEND
        </button>
      </form>
    </div>
  );
};

export default AiTerminal;