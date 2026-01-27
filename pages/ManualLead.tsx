import React, { useState } from 'react';
import { useStore } from '../context/Store';
import { PlusCircle, Save, User, MapPin, Phone, Mail, DollarSign } from 'lucide-react';

const ManualLead: React.FC = () => {
  const { addLead, addLog } = useStore();
  const [formData, setFormData] = useState({
    address: '',
    name: '',
    phone: '',
    email: '',
    arvEstimate: ''
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.address) return;

    const newLead = {
      id: Date.now(),
      address: formData.address,
      name: formData.name || "Unknown",
      phone: formData.phone || "None",
      email: formData.email || "None",
      status: 'New' as const,
      source: 'Manual Entry',
      emailedCount: 0,
      createdAt: new Date().toISOString(),
      arvEstimate: parseInt(formData.arvEstimate) || 0,
      repairEstimate: 0
    };

    addLead(newLead);
    addLog(`📝 MANUAL ENTRY: Added ${formData.address}`, 'success');
    
    // Reset form
    setFormData({ address: '', name: '', phone: '', email: '', arvEstimate: '' });
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="bg-slate-800 border border-slate-700 rounded-lg shadow-xl overflow-hidden">
        <div className="p-6 border-b border-slate-700 bg-slate-900/50">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <PlusCircle className="text-emerald-500" />
            Manual Lead Entry
          </h2>
          <p className="text-slate-400 text-sm mt-1">Input off-market property details directly into the pipeline.</p>
        </div>

        <form onSubmit={handleSubmit} className="p-8 space-y-6">
          
          <div>
            <label className="block text-xs font-bold text-slate-400 mb-2 uppercase flex items-center gap-2">
              <MapPin size={14} /> Property Address
            </label>
            <input 
              type="text" 
              name="address"
              value={formData.address}
              onChange={handleChange}
              placeholder="123 Main St, City, State, Zip"
              className="w-full bg-slate-900 border border-slate-700 rounded p-3 text-white focus:border-emerald-500 outline-none"
              required
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-xs font-bold text-slate-400 mb-2 uppercase flex items-center gap-2">
                <User size={14} /> Owner Name
              </label>
              <input 
                type="text" 
                name="name"
                value={formData.name}
                onChange={handleChange}
                placeholder="John Doe"
                className="w-full bg-slate-900 border border-slate-700 rounded p-3 text-white focus:border-emerald-500 outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-400 mb-2 uppercase flex items-center gap-2">
                <DollarSign size={14} /> Est. Value (ARV)
              </label>
              <input 
                type="number" 
                name="arvEstimate"
                value={formData.arvEstimate}
                onChange={handleChange}
                placeholder="0"
                className="w-full bg-slate-900 border border-slate-700 rounded p-3 text-white focus:border-emerald-500 outline-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-xs font-bold text-slate-400 mb-2 uppercase flex items-center gap-2">
                <Phone size={14} /> Phone Number
              </label>
              <input 
                type="tel" 
                name="phone"
                value={formData.phone}
                onChange={handleChange}
                placeholder="(555) 555-5555"
                className="w-full bg-slate-900 border border-slate-700 rounded p-3 text-white focus:border-emerald-500 outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-400 mb-2 uppercase flex items-center gap-2">
                <Mail size={14} /> Email Address
              </label>
              <input 
                type="email" 
                name="email"
                value={formData.email}
                onChange={handleChange}
                placeholder="owner@example.com"
                className="w-full bg-slate-900 border border-slate-700 rounded p-3 text-white focus:border-emerald-500 outline-none"
              />
            </div>
          </div>

          <div className="pt-4 border-t border-slate-700">
            <button 
              type="submit"
              className="bg-emerald-600 hover:bg-emerald-500 text-white px-8 py-3 rounded font-medium flex items-center gap-2 transition-colors shadow-lg shadow-emerald-900/20"
            >
              <Save size={18} />
              Add to Pipeline
            </button>
          </div>

        </form>
      </div>
    </div>
  );
};

export default ManualLead;
