import React, { useState } from 'react';
import { useStore } from '../context/Store';
import { BoxSelect, Save, Target, DollarSign, Map, Home } from 'lucide-react';

const BuyBox: React.FC = () => {
  const { user, updateUser, addLog } = useStore();
  
  const [formData, setFormData] = useState({
    bbLocations: user?.bbLocations || '',
    bbMinPrice: user?.bbMinPrice || 0,
    bbMaxPrice: user?.bbMaxPrice || 500000,
    bbPropertyType: user?.bbPropertyType || 'Single Family',
    bbCondition: user?.bbCondition || 'Distressed',
    bbStrategy: user?.bbStrategy || 'Fix and Flip'
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: name.includes('Price') ? parseInt(value) || 0 : value
    }));
  };

  const handleSave = () => {
    updateUser(formData);
    addLog("🎯 BUY BOX: Acquisition criteria updated.", "success");
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="bg-slate-800 border border-slate-700 rounded-lg shadow-xl overflow-hidden">
        <div className="p-6 border-b border-slate-700 bg-slate-900/50">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <BoxSelect className="text-emerald-500" />
            Industrial Buy Box
          </h2>
          <p className="text-slate-400 text-sm mt-1">Define your automated acquisition parameters.</p>
        </div>

        <div className="p-8 space-y-8">
          
          {/* Location & Type */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-xs font-bold text-slate-400 mb-2 uppercase flex items-center gap-2">
                <Map size={14} /> Target Markets
              </label>
              <input 
                type="text" 
                name="bbLocations"
                value={formData.bbLocations}
                onChange={handleChange}
                placeholder="e.g. Austin, Dallas, Houston"
                className="w-full bg-slate-900 border border-slate-700 rounded p-3 text-white focus:border-emerald-500 outline-none"
              />
              <p className="text-[10px] text-slate-500 mt-1">Comma separated cities or zip codes.</p>
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-400 mb-2 uppercase flex items-center gap-2">
                <Home size={14} /> Asset Class
              </label>
              <select 
                name="bbPropertyType"
                value={formData.bbPropertyType}
                onChange={handleChange}
                className="w-full bg-slate-900 border border-slate-700 rounded p-3 text-white focus:border-emerald-500 outline-none"
              >
                <option>Single Family</option>
                <option>Multi-Family (2-4)</option>
                <option>Commercial</option>
                <option>Land</option>
              </select>
            </div>
          </div>

          {/* Pricing */}
          <div className="bg-slate-900/50 p-6 rounded-lg border border-slate-700">
            <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider mb-4 flex items-center gap-2">
              <DollarSign size={16} className="text-emerald-500" /> Financial Constraints
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-2">Min Price</label>
                <input 
                  type="number" 
                  name="bbMinPrice"
                  value={formData.bbMinPrice}
                  onChange={handleChange}
                  className="w-full bg-slate-800 border border-slate-600 rounded p-3 text-white focus:border-emerald-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-2">Max Allowable Offer (MAO)</label>
                <input 
                  type="number" 
                  name="bbMaxPrice"
                  value={formData.bbMaxPrice}
                  onChange={handleChange}
                  className="w-full bg-slate-800 border border-slate-600 rounded p-3 text-white focus:border-emerald-500 outline-none"
                />
              </div>
            </div>
          </div>

          {/* Strategy */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-xs font-bold text-slate-400 mb-2 uppercase flex items-center gap-2">
                <Target size={14} /> Condition
              </label>
              <select 
                name="bbCondition"
                value={formData.bbCondition}
                onChange={handleChange}
                className="w-full bg-slate-900 border border-slate-700 rounded p-3 text-white focus:border-emerald-500 outline-none"
              >
                <option>Distressed (Heavy Rehab)</option>
                <option>Cosmetic Updates</option>
                <option>Turnkey</option>
                <option>Shell / Gut Job</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-400 mb-2 uppercase flex items-center gap-2">
                <Target size={14} /> Exit Strategy
              </label>
              <select 
                name="bbStrategy"
                value={formData.bbStrategy}
                onChange={handleChange}
                className="w-full bg-slate-900 border border-slate-700 rounded p-3 text-white focus:border-emerald-500 outline-none"
              >
                <option>Fix and Flip</option>
                <option>Buy and Hold (Rental)</option>
                <option>Wholesale</option>
                <option>BRRRR</option>
              </select>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-700">
            <button 
              onClick={handleSave}
              className="w-full md:w-auto bg-emerald-600 hover:bg-emerald-500 text-white px-8 py-3 rounded font-medium flex items-center justify-center gap-2 transition-colors shadow-lg shadow-emerald-900/20"
            >
              <Save size={18} />
              Save Criteria
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BuyBox;