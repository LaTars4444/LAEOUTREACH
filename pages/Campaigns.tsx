import React, { useState, useEffect } from 'react';
import { useStore } from '../context/Store';
import { Send, Save, Edit3, CheckCircle, AlertTriangle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const Campaigns: React.FC = () => {
  const { user, leads, updateUser, addLog, recordOutreach } = useStore();
  const navigate = useNavigate();
  const [subject, setSubject] = useState("Cash offer for [[ADDRESS]]");
  const [template, setTemplate] = useState(user?.emailTemplate || "");
  const [isSending, setIsSending] = useState(false);
  const [previewLead, setPreviewLead] = useState(leads[0] || null);

  // Paywall Check
  useEffect(() => {
    if (user && !user.hasEmailAccess) {
      addLog("⛔ ACCESS DENIED: Email Machine module required.", "error");
      navigate('/paywall');
    }
  }, [user, navigate, addLog]);

  useEffect(() => {
    if (user?.emailTemplate) setTemplate(user.emailTemplate);
  }, [user]);

  if (!user?.hasEmailAccess) return null;

  const handleSaveTemplate = () => {
    updateUser({ emailTemplate: template });
    addLog("Universal Outreach Script Saved!", "success");
  };

  const handleBlast = async () => {
    if (!user?.smtpEmail) {
      addLog("❌ SMTP CRITICAL ERROR: No SMTP configuration found. Please configure Settings.", "error");
      return;
    }

    const targets = leads.filter(l => l.status === 'New' || l.status === 'Contacted');
    if (targets.length === 0) {
      addLog("⚠️ No targets available for outreach.", "warning");
      return;
    }

    setIsSending(true);
    addLog(`📧 BLAST STARTING: Targeting ${targets.length} potential sellers.`, "info");

    // Simulate sending process
    for (let i = 0; i < targets.length; i++) {
      const lead = targets[i];
      
      // 1. Attempt Real Backend Send
      try {
        const response = await fetch('/api/send-email', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            to: lead.email,
            subject: subject.replace('[[ADDRESS]]', lead.address),
            body: template.replace('[[ADDRESS]]', lead.address).replace('[[NAME]]', lead.name),
            smtp_email: user.smtpEmail,
            smtp_password: user.smtpPassword
          })
        });

        if (response.ok) {
           addLog(`📨 SENT (SMTP): ${lead.email}`, "success");
        } else {
           // Fallback to simulation if backend route is missing (404) or fails
           throw new Error("Backend route not found or failed");
        }
      } catch (e) {
        // 2. Fallback to Simulation with Warning
        addLog(`⚠️ SIMULATION (Backend Offline): Logged send to ${lead.email}`, "warning");
        await new Promise(resolve => setTimeout(resolve, 1000)); // Fake delay
      }

      const finalBody = template
        .replace('[[ADDRESS]]', lead.address)
        .replace('[[NAME]]', lead.name);

      recordOutreach({
        id: Date.now() + i,
        recipientEmail: lead.email,
        address: lead.address,
        message: finalBody,
        sentAt: new Date().toISOString(),
        status: 'Sent'
      });
    }

    addLog("🏁 OUTREACH COMPLETE.", "info");
    setIsSending(false);
  };

  const getPreview = () => {
    if (!previewLead) return "No leads available for preview.";
    return template
      .replace('[[ADDRESS]]', previewLead.address)
      .replace('[[NAME]]', previewLead.name);
  };

  return (
    <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-8">
      <div className="space-y-6">
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-6 shadow-lg">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Edit3 className="text-blue-400" />
              Script Editor
            </h2>
            <button 
              onClick={handleSaveTemplate}
              className="text-xs bg-slate-700 hover:bg-slate-600 text-white px-3 py-1.5 rounded flex items-center gap-1 transition-colors"
            >
              <Save size={14} /> Save Template
            </button>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1 uppercase">Subject Line</label>
              <input 
                type="text" 
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded p-3 text-white focus:border-blue-500 outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1 uppercase">Message Body</label>
              <textarea 
                value={template}
                onChange={(e) => setTemplate(e.target.value)}
                rows={10}
                className="w-full bg-slate-900 border border-slate-700 rounded p-3 text-white focus:border-blue-500 outline-none font-mono text-sm"
              />
              <p className="text-xs text-slate-500 mt-2">
                Available Variables: <span className="text-emerald-500">[[NAME]]</span>, <span className="text-emerald-500">[[ADDRESS]]</span>
              </p>
            </div>
          </div>
        </div>

        <div className="bg-slate-800 border border-slate-700 rounded-lg p-6 shadow-lg">
          <h3 className="text-lg font-bold text-white mb-4">Campaign Controls</h3>
          
          <div className="bg-amber-500/10 border border-amber-500/20 rounded p-3 mb-4 flex items-start gap-2">
             <AlertTriangle className="text-amber-500 shrink-0 mt-0.5" size={16} />
             <div className="text-xs text-amber-200">
               <strong>Backend Connection Required:</strong> If the Python backend is not running or the <code>/api/send-email</code> route is missing, this will default to <strong>Simulation Mode</strong> (logs only, no real emails sent).
             </div>
          </div>

          <div className="flex items-center justify-between bg-slate-900 p-4 rounded mb-6">
            <div>
              <div className="text-sm text-slate-400">Target Audience</div>
              <div className="text-xl font-bold text-white">{leads.filter(l => l.status !== 'Dead').length} Leads</div>
            </div>
            <div className="text-right">
              <div className="text-sm text-slate-400">Est. Duration</div>
              <div className="text-xl font-bold text-white">~{(leads.length * 5) / 60} Mins</div>
            </div>
          </div>
          
          <button
            onClick={handleBlast}
            disabled={isSending}
            className={`w-full py-3 rounded font-bold text-lg flex items-center justify-center gap-2 transition-all
              ${isSending 
                ? 'bg-slate-700 text-slate-400 cursor-not-allowed' 
                : 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg hover:shadow-blue-500/20'
              }`}
          >
            {isSending ? 'PROCESSING BATCH...' : (
              <>
                <Send size={20} /> LAUNCH CAMPAIGN
              </>
            )}
          </button>
        </div>
      </div>

      <div className="space-y-6">
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-6 shadow-lg h-full">
          <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
            <CheckCircle className="text-emerald-400" />
            Live Preview
          </h2>
          
          <div className="bg-white text-slate-900 rounded-lg p-6 shadow-inner min-h-[400px]">
            <div className="border-b border-slate-200 pb-4 mb-4">
              <div className="text-sm text-slate-500 mb-1">To: <span className="text-slate-800 font-medium">{previewLead?.email || 'recipient@example.com'}</span></div>
              <div className="text-sm text-slate-500">Subject: <span className="text-slate-800 font-medium">{subject.replace('[[ADDRESS]]', previewLead?.address || '123 Main St')}</span></div>
            </div>
            <div className="whitespace-pre-wrap font-sans text-sm leading-relaxed">
              {getPreview()}
            </div>
          </div>

          <div className="mt-4 flex justify-end">
             <button 
               onClick={() => {
                 const idx = leads.indexOf(previewLead as any);
                 const next = leads[idx + 1] || leads[0];
                 setPreviewLead(next);
               }}
               className="text-sm text-slate-400 hover:text-white underline"
             >
               Next Preview &rarr;
             </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Campaigns;
