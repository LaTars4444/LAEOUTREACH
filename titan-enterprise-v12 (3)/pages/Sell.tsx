import React, { useState } from 'react';
import { useStore } from '../context/Store';
import { Home, DollarSign, Send, CheckCircle, ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';

const Sell: React.FC = () => {
  const { addLead, addLog } = useStore();
  const [submitted, setSubmitted] = useState(false);
  const [formData, setFormData] = useState({
    address: '',
    name: '',
    email: '',
    phone: '',
    askingPrice: '',
    condition: 'Fair',
    propertyType: 'Single Family'
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    // Create a new lead from the submission
    const newLead = {
      id: Date.now(),
      address: formData.address,
      name: formData.name,
      phone: formData.phone,
      email: formData.email,
      status: 'New' as const,
      source: 'Web Form Submission',
      emailedCount: 0,
      createdAt: new Date().toISOString(),
      askingPrice: parseInt(formData.askingPrice) || 0,
      arvEstimate: 0, // Would be calculated by backend
      repairEstimate: 0
    };

    addLead(newLead);
    // Log this even if user isn't logged in (simulating backend log)
    console.log(`[${new Date().toLocaleTimeString()}] 📥 INBOUND LEAD: ${formData.address}`);
    
    setSubmitted(true);
  };

  if (submitted) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-slate-900 border border-slate-800 rounded-xl p-8 text-center shadow-2xl">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-emerald-500/10 mb-6">
            <CheckCircle className="text-emerald-500" size={40} />
          </div>
          <h2 className="text-2xl font-bold text-white mb-2">Submission Received</h2>
          <p className="text-slate-400 mb-8">
            Thank you. Our acquisition team is analyzing your property data. We will contact you within 24 hours if it meets our Buy Box criteria.
          </p>
          <Link to="/login" className="text-emerald-500 hover:text-emerald-400 font-medium flex items-center justify-center gap-2">
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
              <h1 className="text-2xl font-bold text-white tracking-tight">Sell Your Property</h1>
              <p className="text-slate-500 text-sm mt-1">Get a fair cash offer. No fees, no repairs.</p>
            </div>
            <div className="p-3 bg-blue-500/10 rounded-lg">
              <Home className="text-blue-500" size={24} />
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="p-8 space-y-6">
          <div className="space-y-4">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-800 pb-2">Property Details</h3>
            
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Property Address</label>
              <input 
                type="text" 
                name="address"
                required
                value={formData.address}
                onChange={handleChange}
                placeholder="123 Main St, City, State"
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-white focus:border-blue-500 outline-none"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Property Type</label>
                <select 
                  name="propertyType"
                  value={formData.propertyType}
                  onChange={handleChange}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-white focus:border-blue-500 outline-none"
                >
                  <option>Single Family</option>
                  <option>Multi-Family</option>
                  <option>Commercial</option>
                  <option>Land</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Condition</label>
                <select 
                  name="condition"
                  value={formData.condition}
                  onChange={handleChange}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-white focus:border-blue-500 outline-none"
                >
                  <option>Excellent</option>
                  <option>Fair</option>
                  <option>Poor (Needs Repairs)</option>
                  <option>Distressed (Uninhabitable)</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Asking Price (Optional)</label>
              <div className="relative">
                <DollarSign className="absolute left-3 top-3.5 text-slate-600" size={16} />
                <input 
                  type="number" 
                  name="askingPrice"
                  value={formData.askingPrice}
                  onChange={handleChange}
                  placeholder="0.00"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 pl-9 text-white focus:border-blue-500 outline-none"
                />
              </div>
            </div>
          </div>

          <div className="space-y-4 pt-4">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-800 pb-2">Contact Info</h3>
            
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Full Name</label>
              <input 
                type="text" 
                name="name"
                required
                value={formData.name}
                onChange={handleChange}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-white focus:border-blue-500 outline-none"
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
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-white focus:border-blue-500 outline-none"
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
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-white focus:border-blue-500 outline-none"
                />
              </div>
            </div>
          </div>

          <div className="pt-4 flex items-center justify-between">
            <Link to="/login" className="text-sm text-slate-500 hover:text-white transition-colors">
              Cancel
            </Link>
            <button 
              type="submit"
              className="bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 px-8 rounded-lg transition-all flex items-center gap-2 shadow-lg shadow-blue-900/20"
            >
              <Send size={18} />
              Submit Property
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Sell;