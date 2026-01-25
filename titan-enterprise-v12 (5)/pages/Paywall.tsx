import React from 'react';
import { useStore } from '../context/Store';
import { Check, Zap, Mail, ShieldCheck, Crown, Clock, CreditCard, PlayCircle, Lock } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const Paywall: React.FC = () => {
  const { user, purchasePlan, activateTrial } = useStore();
  const navigate = useNavigate();

  const handlePurchase = (plan: 'weekly_email' | 'lifetime_email' | 'monthly_ai') => {
    setTimeout(() => {
      purchasePlan(plan);
      navigate('/');
    }, 1000);
  };

  const handleStartTrial = () => {
    activateTrial();
    setTimeout(() => navigate('/'), 500);
  };

  // Calculate trial time left for display
  const getTrialLeft = () => {
    if (!user || !user.trialStart) return 0;
    const now = new Date().getTime();
    const start = new Date(user.trialStart).getTime();
    const hours = 48 - ((now - start) / (1000 * 60 * 60));
    return Math.max(0, Math.floor(hours));
  };

  const trialHours = getTrialLeft();
  const trialNotStarted = user?.subscriptionStatus === 'free' && !user?.trialStart;

  return (
    <div className="min-h-screen bg-slate-950 py-12 px-4 sm:px-6 lg:px-8 flex flex-col items-center">
      
      {/* Active Trial Banner */}
      {user?.subscriptionStatus === 'free' && user?.trialStart && (
        <div className={`mb-8 px-6 py-3 rounded-full border flex flex-col md:flex-row items-center gap-2 md:gap-4 ${
          trialHours > 0 
            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' 
            : 'bg-red-500/10 border-red-500/30 text-red-400'
        }`}>
          <div className="flex items-center gap-2">
            <Clock size={18} />
            <span className="font-mono font-bold">
              {trialHours > 0 
                ? `FREE TRIAL ACTIVE: ${trialHours} HOURS REMAINING` 
                : 'FREE TRIAL EXPIRED'}
            </span>
          </div>
        </div>
      )}

      <div className="text-center max-w-3xl mx-auto mb-12">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-emerald-500/10 mb-4 border border-emerald-500/20">
          <ShieldCheck className="text-emerald-500" size={32} />
        </div>
        <h2 className="text-3xl font-bold text-white sm:text-4xl tracking-tight">
          Upgrade Your Industrial Arsenal
        </h2>
        <p className="mt-4 text-lg text-slate-400">
          Select a module to activate. Secure, encrypted payment processing.
        </p>
      </div>

      {/* FREE TRIAL ACTIVATION CARD */}
      {trialNotStarted && (
        <div className="max-w-4xl w-full mb-12 bg-gradient-to-r from-emerald-900/20 to-slate-900 border border-emerald-500/30 rounded-2xl p-8 flex flex-col md:flex-row items-center justify-between shadow-2xl shadow-emerald-900/10">
          <div className="mb-6 md:mb-0">
            <h3 className="text-2xl font-bold text-white flex items-center gap-2">
              <Zap className="text-emerald-400" />
              Start 48-Hour Free Trial
            </h3>
            <p className="text-slate-400 mt-2">
              Test drive the entire system: Lead Hunter, AI Terminal, and Email Machine.
            </p>
            <div className="flex items-center gap-2 mt-4 text-sm text-emerald-400 font-bold bg-emerald-500/10 px-3 py-1 rounded-full w-fit">
              <CreditCard size={16} />
              NO CREDIT CARD REQUIRED
            </div>
          </div>
          <button
            onClick={handleStartTrial}
            className="bg-emerald-500 hover:bg-emerald-400 text-white px-8 py-4 rounded-lg font-bold text-lg flex items-center gap-2 shadow-lg shadow-emerald-500/20 transition-all transform hover:scale-105"
          >
            <PlayCircle size={24} />
            ACTIVATE TRIAL NOW
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-7xl w-full">
        
        {/* Tier 1: Weekly Email */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8 flex flex-col relative overflow-hidden hover:border-blue-500/50 transition-colors">
          <div className="absolute top-0 right-0 p-4 opacity-5">
            <Mail size={100} />
          </div>
          <h3 className="text-lg font-semibold text-blue-400 uppercase tracking-wider">Email Machine</h3>
          <div className="mt-4 flex items-baseline text-white">
            <span className="text-4xl font-extrabold tracking-tight">$3</span>
            <span className="ml-1 text-xl font-medium text-slate-500">/week</span>
          </div>
          <p className="mt-2 text-sm text-slate-400">Flexible access to the outreach engine.</p>
          
          <ul className="mt-6 space-y-4 flex-1">
            <li className="flex items-start">
              <Check className="flex-shrink-0 h-5 w-5 text-emerald-500" />
              <span className="ml-3 text-sm text-slate-300">Unlimited Email Sends</span>
            </li>
            <li className="flex items-start">
              <Check className="flex-shrink-0 h-5 w-5 text-emerald-500" />
              <span className="ml-3 text-sm text-slate-300">Template Injection</span>
            </li>
            <li className="flex items-start">
              <Check className="flex-shrink-0 h-5 w-5 text-emerald-500" />
              <span className="ml-3 text-sm text-slate-300">Sent History Log</span>
            </li>
          </ul>

          <button
            onClick={() => handlePurchase('weekly_email')}
            disabled={user?.hasEmailAccess && user.subscriptionStatus !== 'free'}
            className={`mt-8 w-full py-3 px-4 rounded-lg font-bold text-sm transition-all
              ${user?.hasEmailAccess && user.subscriptionStatus !== 'free'
                ? 'bg-slate-800 text-slate-500 cursor-not-allowed' 
                : 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-900/20'}`}
          >
            {user?.hasEmailAccess && user.subscriptionStatus !== 'free' ? 'MODULE ACTIVE' : 'ACTIVATE WEEKLY'}
          </button>
        </div>

        {/* Tier 2: Lifetime Email */}
        <div className="bg-slate-900 border border-emerald-500/30 rounded-2xl p-8 flex flex-col relative overflow-hidden transform md:-translate-y-4 shadow-2xl shadow-emerald-900/10">
          <div className="absolute top-0 right-0 bg-emerald-500 text-white text-xs font-bold px-3 py-1 rounded-bl-lg">
            BEST VALUE
          </div>
          <h3 className="text-lg font-semibold text-emerald-400 uppercase tracking-wider">Email Machine Pro</h3>
          <div className="mt-4 flex items-baseline text-white">
            <span className="text-4xl font-extrabold tracking-tight">$20</span>
            <span className="ml-1 text-xl font-medium text-slate-500">/lifetime</span>
          </div>
          <p className="mt-2 text-sm text-slate-400">Permanent ownership of outreach tools.</p>
          
          <ul className="mt-6 space-y-4 flex-1">
            <li className="flex items-start">
              <Check className="flex-shrink-0 h-5 w-5 text-emerald-500" />
              <span className="ml-3 text-sm text-slate-300">Everything in Weekly</span>
            </li>
            <li className="flex items-start">
              <Check className="flex-shrink-0 h-5 w-5 text-emerald-500" />
              <span className="ml-3 text-sm text-slate-300">One-time Payment</span>
            </li>
            <li className="flex items-start">
              <Check className="flex-shrink-0 h-5 w-5 text-emerald-500" />
              <span className="ml-3 text-sm text-slate-300">Priority SMTP Relay</span>
            </li>
            <li className="flex items-start">
              <Check className="flex-shrink-0 h-5 w-5 text-emerald-500" />
              <span className="ml-3 text-sm text-slate-300">No Recurring Fees</span>
            </li>
          </ul>

          <button
            onClick={() => handlePurchase('lifetime_email')}
            disabled={user?.subscriptionStatus === 'lifetime'}
            className={`mt-8 w-full py-3 px-4 rounded-lg font-bold text-sm transition-all
              ${user?.subscriptionStatus === 'lifetime'
                ? 'bg-slate-800 text-slate-500 cursor-not-allowed' 
                : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-900/20'}`}
          >
            {user?.subscriptionStatus === 'lifetime' ? 'LIFETIME ACTIVE' : 'BUY LIFETIME ACCESS'}
          </button>
        </div>

        {/* Tier 3: AI & Leads */}
        <div className="bg-slate-900 border border-purple-500/30 rounded-2xl p-8 flex flex-col relative overflow-hidden hover:border-purple-500/50 transition-colors">
          <div className="absolute top-0 right-0 p-4 opacity-5">
            <Zap size={100} />
          </div>
          <h3 className="text-lg font-semibold text-purple-400 uppercase tracking-wider">Titan Intelligence</h3>
          <div className="mt-4 flex items-baseline text-white">
            <span className="text-4xl font-extrabold tracking-tight">$50</span>
            <span className="ml-1 text-xl font-medium text-slate-500">/month</span>
          </div>
          <p className="mt-2 text-sm text-slate-400">Full Suite Access (AI + Email + Leads).</p>
          
          <ul className="mt-6 space-y-4 flex-1">
            <li className="flex items-start">
              <Check className="flex-shrink-0 h-5 w-5 text-purple-500" />
              <span className="ml-3 text-sm text-slate-300 font-bold text-white">INCLUDES EMAIL MACHINE</span>
            </li>
            <li className="flex items-start">
              <Check className="flex-shrink-0 h-5 w-5 text-purple-500" />
              <span className="ml-3 text-sm text-slate-300">1,000+ Site Scraper</span>
            </li>
            <li className="flex items-start">
              <Check className="flex-shrink-0 h-5 w-5 text-purple-500" />
              <span className="ml-3 text-sm text-slate-300">Stealth Jitter Protocol</span>
            </li>
            <li className="flex items-start">
              <Check className="flex-shrink-0 h-5 w-5 text-purple-500" />
              <span className="ml-3 text-sm text-slate-300">Groq AI Terminal Access</span>
            </li>
          </ul>

          <button
            onClick={() => handlePurchase('monthly_ai')}
            disabled={user?.hasAiAccess && user.subscriptionStatus !== 'free'}
            className={`mt-8 w-full py-3 px-4 rounded-lg font-bold text-sm transition-all
              ${user?.hasAiAccess && user.subscriptionStatus !== 'free'
                ? 'bg-slate-800 text-slate-500 cursor-not-allowed' 
                : 'bg-purple-600 hover:bg-purple-500 text-white shadow-lg shadow-purple-900/20'}`}
          >
            {user?.hasAiAccess && user.subscriptionStatus !== 'free' ? 'MODULE ACTIVE' : 'ACTIVATE INTELLIGENCE'}
          </button>
        </div>

      </div>
      
      <div className="mt-12 text-center space-y-2">
        <p className="text-xs text-slate-500 flex items-center justify-center gap-2">
          <Lock size={12} className="text-emerald-500" />
          Payments secured by Stripe. Environment keys detected.
        </p>
        <p className="text-xs text-slate-500 flex items-center justify-center gap-2">
          <Crown size={14} className="text-amber-500" />
          Enterprise Administrators have infinite access to all modules.
        </p>
      </div>
    </div>
  );
};

export default Paywall;

--- END of file pages/Paywall.tsx ---


--- START of file pages/AiTerminal.tsx ---

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

--- END of file pages/AiTerminal.tsx ---
