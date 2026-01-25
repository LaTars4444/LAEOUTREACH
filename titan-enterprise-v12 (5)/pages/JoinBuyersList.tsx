import React, { useState } from 'react';
import { useStore } from '../context/Store';
import { Briefcase, DollarSign, CheckCircle, ArrowLeft, Map, Target } from 'lucide-react';
import { Link } from 'react-router-dom';

const JoinBuyersList: React.FC = () => {
  const { addInvestor } = useStore();
  const [submitted, setSubmitted] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    markets: '',
    minPrice: '',
    maxPrice: '',
    assetClass: 'Single Family',
    strategy: 'Fix and Flip'
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    const newInvestor = {
      id: Date.now(),
      name: formData.name,
      email: formData.email,
      phone: formData.phone,
      markets: formData.markets,
      minPrice: parseInt(formData.minPrice) || 0,
      maxPrice: parseInt(formData.maxPrice) || 0,
      assetClass: formData.assetClass,
      strategy: formData.strategy,
      createdAt: new Date().toISOString()
    };

    addInvestor(newInvestor);
    console.log(`[${new Date().toLocaleTimeString()}] 🤝 NEW INVESTOR: ${formData.email}`);
    setSubmitted(true);
  };

  if (submitted) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-slate-900 border border-slate-800 rounded-xl p-8 text-center shadow-2xl">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-purple-500/10 mb-6">
            <CheckCircle className="text-purple-500" size={40} />
          </div>
          <h2 className="text-2xl font-bold text-white mb-2">You're on the List!</h2>
          <p className="text-slate-400 mb-8">
            We have received your buying criteria. You will be the first to know when we secure off-market deals that match your buy box.
          </p>
          <Link to="/login" className="text-purple-500 hover:text-purple-400 font-medium flex items-center justify-center gap-2">
            <ArrowLeft size={16} /> Return to Portal
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="max-w-2xl w-full bg-slate-900 border border-slate-800 rounded-xl shadow-2xl overflow-hidden">
        <div className="p-8 border-b border-slate-800 bg-slate-900">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">Join Buyers List</h1>
              <p className="text-slate-500 text-sm mt-1">Get exclusive access to off-market deals.</p>
            </div>
            <div className="p-3 bg-purple-500/10 rounded-lg">
              <Briefcase className="text-purple-500" size={24} />
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="p-8 space-y-6">
          
          {/* Contact Info */}
          <div className="space-y-4">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-800 pb-2">Investor Profile</h3>
            
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Full Name / Entity</label>
              <input 
                type="text" 
                name="name"
                required
                value={formData.name}
                onChange={handleChange}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-white focus:border-purple-500 outline-none"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Email Address</label>
                <input 
                  type="email" 
                  name="email"
                  required
                  value={formData.email}
                  onChange={handleChange}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-white focus:border-purple-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Phone Number</label>
                <input 
                  type="tel" 
                  name="phone"
                  required
                  value={formData.phone}
                  onChange={handleChange}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-white focus:border-purple-500 outline-none"
                />
              </div>
            </div>
          </div>

          {/* Buy Box Criteria */}
          <div className="space-y-4 pt-4">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-800 pb-2">Acquisition Criteria</h3>
            
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1 flex items-center gap-2">
                <Map size={14} /> Target Markets (Cities/Zips)
              </label>
              <input 
                type="text" 
                name="markets"
                required
                value={formData.markets}
                onChange={handleChange}
                placeholder="e.g. Houston, Phoenix, 90210"
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-white focus:border-purple-500 outline-none"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Asset Class</label>
                <select 
                  name="assetClass"
                  value={formData.assetClass}
                  onChange={handleChange}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-white focus:border-purple-500 outline-none"
                >
                  <option>Single Family</option>
                  <option>Multi-Family</option>
                  <option>Commercial</option>
                  <option>Land</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Strategy</label>
                <select 
                  name="strategy"
                  value={formData.strategy}
                  onChange={handleChange}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-white focus:border-purple-500 outline-none"
                >
                  <option>Fix and Flip</option>
                  <option>Buy and Hold</option>
                  <option>Wholesale</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Min Price</label>
                <div className="relative">
                  <DollarSign className="absolute left-3 top-3.5 text-slate-600" size={16} />
                  <input 
                    type="number" 
                    name="minPrice"
                    value={formData.minPrice}
                    onChange={handleChange}
                    placeholder="0"
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 pl-9 text-white focus:border-purple-500 outline-none"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Max Price</label>
                <div className="relative">
                  <DollarSign className="absolute left-3 top-3.5 text-slate-600" size={16} />
                  <input 
                    type="number" 
                    name="maxPrice"
                    value={formData.maxPrice}
                    onChange={handleChange}
                    placeholder="1000000"
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 pl-9 text-white focus:border-purple-500 outline-none"
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="pt-4 flex items-center justify-between">
            <Link to="/login" className="text-sm text-slate-500 hover:text-white transition-colors">
              Cancel
            </Link>
            <button 
              type="submit"
              className="bg-purple-600 hover:bg-purple-500 text-white font-bold py-3 px-8 rounded-lg transition-all flex items-center gap-2 shadow-lg shadow-purple-900/20"
            >
              <CheckCircle size={18} />
              Join List
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default JoinBuyersList;