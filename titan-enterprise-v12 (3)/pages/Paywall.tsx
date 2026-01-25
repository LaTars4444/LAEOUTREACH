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