import React, { useState } from 'react';
import { useStore } from '../context/Store';
import { ShieldCheck, Lock, Mail, ArrowRight, Home, DollarSign, Briefcase, UserPlus } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';

const Login: React.FC = () => {
  const { login, register } = useStore();
  const navigate = useNavigate();
  const [isRegistering, setIsRegistering] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (email && password) {
      if (isRegistering) {
        register(email);
      } else {
        login(email);
      }
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background Decoration */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0 pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-emerald-500/5 rounded-full blur-3xl"></div>
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-blue-500/5 rounded-full blur-3xl"></div>
      </div>

      <div className="w-full max-w-4xl grid grid-cols-1 md:grid-cols-2 gap-8 z-10">
        
        {/* Operator Login/Register Section */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-2xl overflow-hidden flex flex-col">
          <div className="p-8 text-center border-b border-slate-800 bg-slate-900/50">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-emerald-500/10 mb-4 border border-emerald-500/20">
              <ShieldCheck className="text-emerald-500" size={32} />
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Titan Enterprise</h1>
            <p className="text-slate-500 text-sm mt-2 font-mono">
              {isRegistering ? 'NEW OPERATOR REGISTRATION' : 'OPERATOR ACCESS V12.0.0'}
            </p>
          </div>

          <form onSubmit={handleSubmit} className="p-8 space-y-6 flex-1 flex flex-col justify-center">
            <div>
              <label className="block text-xs font-bold text-slate-400 mb-1 uppercase tracking-wider">Operator ID</label>
              <div className="relative">
                <Mail className="absolute left-3 top-3.5 text-slate-600" size={18} />
                <input 
                  type="email" 
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg py-3 pl-10 pr-4 text-white focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 outline-none transition-all"
                  placeholder="admin@titan.ent"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-400 mb-1 uppercase tracking-wider">Secure Key</label>
              <div className="relative">
                <Lock className="absolute left-3 top-3.5 text-slate-600" size={18} />
                <input 
                  type="password" 
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg py-3 pl-10 pr-4 text-white focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 outline-none transition-all"
                  placeholder="••••••••"
                  required
                />
              </div>
            </div>

            <button 
              type="submit"
              className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-4 rounded-lg transition-all flex items-center justify-center gap-2 shadow-lg shadow-emerald-900/20 group mt-4"
            >
              {isRegistering ? 'CREATE ACCOUNT' : 'INITIALIZE SYSTEM'}
              <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
            </button>

            <div className="text-center pt-4 border-t border-slate-800 mt-4">
              <button 
                type="button"
                onClick={() => setIsRegistering(!isRegistering)}
                className="text-sm font-bold text-purple-400 hover:text-purple-300 transition-colors flex items-center justify-center gap-2 w-full py-2 rounded hover:bg-purple-500/10"
              >
                {isRegistering ? (
                  <>Already have an account? Login</>
                ) : (
                  <>
                    <UserPlus size={16} /> New Operator? Register Here
                  </>
                )}
              </button>
            </div>
          </form>
          
          <div className="px-8 py-4 bg-slate-950 border-t border-slate-800 text-center">
            <p className="text-[10px] text-slate-600 font-mono uppercase">
              Authorized Personnel Only • 256-bit Encryption
            </p>
          </div>
        </div>

        {/* Public Portals Section */}
        <div className="flex flex-col gap-4">
          
          {/* Seller Portal Card */}
          <div className="bg-gradient-to-br from-blue-900/20 to-slate-900 border border-blue-500/20 rounded-xl shadow-xl p-8 flex-1 flex flex-col justify-center relative overflow-hidden">
            <div className="absolute top-0 right-0 p-4 opacity-10">
              <Home size={80} className="text-blue-400" />
            </div>
            <h2 className="text-2xl font-bold text-white mb-2">Selling a Property?</h2>
            <p className="text-slate-400 mb-6 text-sm">
              Get a fair, all-cash offer for your property within 24 hours. No fees, no repairs.
            </p>
            <Link 
              to="/sell" 
              className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 rounded-lg transition-all flex items-center justify-center gap-2 shadow-lg shadow-blue-900/20"
            >
              <DollarSign size={18} /> GET CASH OFFER
            </Link>
          </div>

          {/* Investor Portal Card */}
          <div className="bg-gradient-to-br from-purple-900/20 to-slate-900 border border-purple-500/20 rounded-xl shadow-xl p-8 flex-1 flex flex-col justify-center relative overflow-hidden">
            <div className="absolute top-0 right-0 p-4 opacity-10">
              <Briefcase size={80} className="text-purple-400" />
            </div>
            <h2 className="text-2xl font-bold text-white mb-2">Buying Properties?</h2>
            <p className="text-slate-400 mb-6 text-sm">
              Join our exclusive buyers list to get off-market deals sent directly to your inbox.
            </p>
            <Link 
              to="/investors" 
              className="w-full bg-purple-600 hover:bg-purple-500 text-white font-bold py-3 rounded-lg transition-all flex items-center justify-center gap-2 shadow-lg shadow-purple-900/20"
            >
              <Briefcase size={18} /> JOIN BUYERS LIST
            </Link>
          </div>

        </div>

      </div>
    </div>
  );
};

export default Login;