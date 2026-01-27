import React, { useState } from 'react';
import { useStore } from '../context/Store';
import { Save, Server, Shield, AlertTriangle, Info, ExternalLink, Cpu, CheckCircle2, CreditCard, XCircle, Search, Activity, AlertCircle } from 'lucide-react';

const Settings: React.FC = () => {
  const { user, updateUser, addLog, cancelSubscription } = useStore();
  const [smtpEmail, setSmtpEmail] = useState(user?.smtpEmail || '');
  const [smtpPassword, setSmtpPassword] = useState(user?.smtpPassword || '');
  const [groqApiKey, setGroqApiKey] = useState(user?.groqApiKey || '');
  
  // Diagnostic State
  const [testKey, setTestKey] = useState('');
  const [testCx, setTestCx] = useState('');
  const [testStatus, setTestStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [testResult, setTestResult] = useState('');

  const handleSave = () => {
    updateUser({ smtpEmail, smtpPassword, groqApiKey });
    addLog("⚙️ SETTINGS: Keys updated securely.", "success");
  };

  const runGoogleDiagnostic = async () => {
    if (!testKey || !testCx) {
      setTestResult("Please enter both API Key and CX ID to test.");
      setTestStatus('error');
      return;
    }

    setTestStatus('loading');
    setTestResult("Pinging Google Cloud...");

    try {
      const url = `https://www.googleapis.com/customsearch/v1?key=${testKey}&cx=${testCx}&q=test`;
      const response = await fetch(url);
      const data = await response.json();

      if (data.error) {
        setTestStatus('error');
        setTestResult(`ERROR ${data.error.code}: ${data.error.message}`);
      } else if (data.items) {
        setTestStatus('success');
        setTestResult("SUCCESS! API is active and returning results. Update your Render Environment Variables with these keys.");
      } else {
        setTestStatus('error');
        setTestResult("Connected, but no results returned. Check your CX (Search Engine) configuration.");
      }
    } catch (e: any) {
      setTestStatus('error');
      setTestResult(`NETWORK ERROR: ${e.message}`);
    }
  };

  // Check for system key
  let hasSystemKey = false;
  try {
    if (process.env.GROQ_API_KEY) hasSystemKey = true;
  } catch(e) {}

  // Helper to get plan display name
  const getPlanName = () => {
    switch (user?.subscriptionStatus) {
      case 'weekly': return 'Email Machine (Weekly)';
      case 'monthly': return 'Titan Intelligence (Monthly)';
      case 'lifetime': return 'Lifetime Pro';
      case 'free': return 'Free Trial / Basic';
      default: return 'Unknown';
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="bg-slate-800 border border-slate-700 rounded-lg shadow-xl overflow-hidden">
        <div className="p-6 border-b border-slate-700 bg-slate-900/50">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Server className="text-emerald-500" />
            Industrial Configuration
          </h2>
          <p className="text-slate-400 text-sm mt-1">Manage SMTP relays, AI keys, and billing.</p>
        </div>

        <div className="p-8 space-y-8">
          
          {/* Subscription Management */}
          <div className="bg-slate-900 border border-slate-700 rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <CreditCard size={16} /> Subscription Status
              </h3>
              <span className={`text-xs font-bold px-2 py-1 rounded uppercase ${
                user?.subscriptionStatus === 'free' ? 'bg-slate-700 text-slate-300' : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
              }`}>
                {user?.subscriptionStatus}
              </span>
            </div>
            
            <div className="flex items-center justify-between">
              <div>
                <div className="text-white font-medium text-lg">{getPlanName()}</div>
                {user?.subscriptionStatus === 'free' && user.hasAiAccess && (
                  <div className="text-emerald-400 text-xs mt-1 flex items-center gap-1">
                    <CheckCircle2 size={12} /> 48-Hour Trial Active
                  </div>
                )}
              </div>
              
              {user?.subscriptionStatus !== 'free' && !user?.isAdmin && (
                <button 
                  onClick={cancelSubscription}
                  className="text-red-400 hover:text-red-300 text-sm flex items-center gap-1 hover:underline"
                >
                  <XCircle size={14} /> Cancel Subscription
                </button>
              )}
            </div>
          </div>

          {/* Google Search API Diagnostic Tool */}
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-slate-700 pb-2">
              <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <Search size={16} /> Google API Diagnostic
              </h3>
            </div>
            
            <div className="bg-slate-900 p-4 rounded border border-slate-700 space-y-4">
              <div className="text-xs text-slate-400">
                Paste your keys here to test them immediately. This does not save them to the app; it only tests connectivity.
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <input 
                  type="text" 
                  value={testKey}
                  onChange={(e) => setTestKey(e.target.value)}
                  placeholder="Paste API Key (AIza...)"
                  className="bg-slate-800 border border-slate-600 rounded p-2 text-white text-sm outline-none focus:border-blue-500"
                />
                <input 
                  type="text" 
                  value={testCx}
                  onChange={(e) => setTestCx(e.target.value)}
                  placeholder="Paste CX ID (0123...)"
                  className="bg-slate-800 border border-slate-600 rounded p-2 text-white text-sm outline-none focus:border-blue-500"
                />
              </div>

              <button 
                onClick={runGoogleDiagnostic}
                disabled={testStatus === 'loading'}
                className="w-full bg-blue-600 hover:bg-blue-500 text-white py-2 rounded text-sm font-bold flex items-center justify-center gap-2 transition-colors"
              >
                {testStatus === 'loading' ? <Activity className="animate-spin" size={14} /> : <Activity size={14} />}
                Test Live Connection
              </button>

              {testResult && (
                <div className={`p-3 rounded text-xs font-mono break-all ${
                  testStatus === 'success' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-red-500/20 text-red-400 border border-red-500/30'
                }`}>
                  {testStatus === 'success' ? <CheckCircle2 size={14} className="inline mr-2" /> : <AlertCircle size={14} className="inline mr-2" />}
                  {testResult}
                </div>
              )}
            </div>
          </div>

          {/* SMTP Section */}
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-slate-700 pb-2">
              <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider">
                Gmail SMTP Relay
              </h3>
              <span className="text-[10px] bg-blue-500/20 text-blue-400 px-2 py-1 rounded border border-blue-500/30">
                APP PASSWORD REQUIRED
              </span>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Sender Email (Gmail)</label>
                <input 
                  type="email" 
                  value={smtpEmail}
                  onChange={(e) => setSmtpEmail(e.target.value)}
                  placeholder="investor@company.com"
                  className="w-full bg-slate-900 border border-slate-700 rounded p-3 text-white focus:border-emerald-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">App Password</label>
                <input 
                  type="password" 
                  value={smtpPassword}
                  onChange={(e) => setSmtpPassword(e.target.value)}
                  placeholder="xxxx xxxx xxxx xxxx"
                  className="w-full bg-slate-900 border border-slate-700 rounded p-3 text-white focus:border-emerald-500 outline-none font-mono"
                />
              </div>
            </div>

            <div className="bg-slate-900 p-4 rounded border border-slate-700 flex gap-3">
              <Info className="text-blue-400 shrink-0" size={18} />
              <div className="text-xs text-slate-400 leading-relaxed">
                <strong className="text-slate-300">Security Notice:</strong> Do not use your standard Gmail login password. 
                Google requires an <strong>App Password</strong> for third-party outreach tools.
                <br />
                <a 
                  href="https://myaccount.google.com/apppasswords" 
                  target="_blank" 
                  rel="noreferrer"
                  className="text-emerald-500 hover:underline inline-flex items-center gap-1 mt-1"
                >
                  Generate App Password <ExternalLink size={10} />
                </a>
              </div>
            </div>
          </div>

          {/* Groq AI Section */}
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-slate-700 pb-2">
              <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <Cpu size={16} /> Groq AI Integration
              </h3>
              {hasSystemKey && (
                <span className="flex items-center gap-1 text-[10px] bg-emerald-500/20 text-emerald-400 px-2 py-1 rounded border border-emerald-500/30">
                  <CheckCircle2 size={10} /> SYSTEM KEY DETECTED
                </span>
              )}
            </div>
            
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-2">Groq API Key</label>
              <input 
                type="password" 
                value={groqApiKey}
                onChange={(e) => setGroqApiKey(e.target.value)}
                placeholder={hasSystemKey ? "Using System Key (Override Optional)" : "gsk_..."}
                className="w-full bg-slate-900 border border-slate-700 rounded p-3 text-white focus:border-purple-500 outline-none font-mono"
              />
            </div>
          </div>

          <div className="pt-4">
            <button 
              onClick={handleSave}
              className="bg-emerald-600 hover:bg-emerald-500 text-white px-6 py-3 rounded font-medium flex items-center gap-2 transition-colors shadow-lg shadow-emerald-900/20"
            >
              <Save size={18} />
              Update Configuration
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Settings;
