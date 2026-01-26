import React from 'react';
import { useStore } from '../context/Store';
import Terminal from '../components/Terminal';
import { Users, Mail, Flame, Database, BoxSelect, MapPin, DollarSign, Target } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { Link } from 'react-router-dom';

const StatCard: React.FC<{ title: string; value: string | number; icon: React.ElementType; color: string }> = ({ title, value, icon: Icon, color }) => (
  <div className="bg-slate-800 border border-slate-700 p-6 rounded-lg shadow-lg">
    <div className="flex items-center justify-between mb-4">
      <h3 className="text-slate-400 text-sm font-medium uppercase tracking-wider">{title}</h3>
      <div className={`p-2 rounded-md bg-opacity-10 ${color.replace('text-', 'bg-')}`}>
        <Icon className={color} size={20} />
      </div>
    </div>
    <div className="text-3xl font-bold text-white">{value}</div>
  </div>
);

const Dashboard: React.FC = () => {
  const { leads, outreachHistory, user } = useStore();

  const totalLeads = leads.length;
  const hotLeads = leads.filter(l => l.status === 'Hot').length;
  const contacted = leads.filter(l => l.status === 'Contacted').length;
  const totalSent = outreachHistory.length;

  const chartData = [
    { name: 'New', value: leads.filter(l => l.status === 'New').length },
    { name: 'Contacted', value: contacted },
    { name: 'Hot', value: hotLeads },
    { name: 'Dead', value: leads.filter(l => l.status === 'Dead').length },
  ];

  return (
    <div className="space-y-6">
      {/* Top Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard title="Total Leads" value={totalLeads} icon={Database} color="text-blue-400" />
        <StatCard title="Hot Prospects" value={hotLeads} icon={Flame} color="text-orange-500" />
        <StatCard title="Outreach Sent" value={totalSent} icon={Mail} color="text-emerald-400" />
        <StatCard title="Active Targets" value={totalLeads - contacted} icon={Users} color="text-purple-400" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          
          {/* Buy Box Widget (New Visibility) */}
          <div className="bg-gradient-to-r from-slate-800 to-slate-900 border border-slate-700 p-6 rounded-lg shadow-lg relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity">
              <BoxSelect size={100} className="text-emerald-500" />
            </div>
            <div className="flex justify-between items-start mb-4 relative z-10">
              <div>
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <BoxSelect className="text-emerald-500" size={20} />
                  Active Buy Box Criteria
                </h3>
                <p className="text-slate-400 text-sm">Automated acquisition parameters currently in effect.</p>
              </div>
              <Link to="/buy-box" className="text-xs bg-slate-700 hover:bg-slate-600 text-white px-3 py-1.5 rounded border border-slate-600 transition-colors">
                Edit Criteria
              </Link>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 relative z-10">
              <div className="bg-slate-900/50 p-3 rounded border border-slate-700/50">
                <div className="text-xs text-slate-500 uppercase mb-1 flex items-center gap-1"><MapPin size={10} /> Markets</div>
                <div className="text-sm font-medium text-white truncate">{user?.bbLocations || 'Not Configured'}</div>
              </div>
              <div className="bg-slate-900/50 p-3 rounded border border-slate-700/50">
                <div className="text-xs text-slate-500 uppercase mb-1 flex items-center gap-1"><DollarSign size={10} /> Max Offer</div>
                <div className="text-sm font-medium text-emerald-400">${user?.bbMaxPrice?.toLocaleString() || '0'}</div>
              </div>
              <div className="bg-slate-900/50 p-3 rounded border border-slate-700/50">
                <div className="text-xs text-slate-500 uppercase mb-1 flex items-center gap-1"><Target size={10} /> Strategy</div>
                <div className="text-sm font-medium text-blue-400">{user?.bbStrategy || 'Any'}</div>
              </div>
            </div>
          </div>

          {/* Chart Section */}
          <div className="bg-slate-800 border border-slate-700 p-6 rounded-lg shadow-lg">
            <h3 className="text-lg font-semibold text-white mb-6">Pipeline Velocity</h3>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#f1f5f9' }}
                    itemStyle={{ color: '#f1f5f9' }}
                    cursor={{fill: '#334155', opacity: 0.4}}
                  />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {chartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={['#3b82f6', '#10b981', '#f97316', '#64748b'][index]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Recent Leads Table */}
          <div className="bg-slate-800 border border-slate-700 rounded-lg shadow-lg overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-700 flex justify-between items-center">
              <h3 className="text-lg font-semibold text-white">Recent Acquisitions</h3>
              <span className="text-xs text-emerald-500 bg-emerald-500/10 px-2 py-1 rounded border border-emerald-500/20">LIVE DATA</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left text-slate-300">
                <thead className="text-xs text-slate-400 uppercase bg-slate-900/50">
                  <tr>
                    <th className="px-6 py-3">Address</th>
                    <th className="px-6 py-3">Owner</th>
                    <th className="px-6 py-3">Status</th>
                    <th className="px-6 py-3">Est. ARV</th>
                  </tr>
                </thead>
                <tbody>
                  {leads.slice(0, 5).map((lead) => (
                    <tr key={lead.id} className="border-b border-slate-700 hover:bg-slate-700/50 transition-colors">
                      <td className="px-6 py-4 font-medium text-white">{lead.address}</td>
                      <td className="px-6 py-4">{lead.name}</td>
                      <td className="px-6 py-4">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium
                          ${lead.status === 'Hot' ? 'bg-orange-500/20 text-orange-400' : 
                            lead.status === 'Contacted' ? 'bg-blue-500/20 text-blue-400' : 
                            'bg-slate-600/20 text-slate-400'}`}>
                          {lead.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 font-mono text-emerald-400">
                        ${lead.arvEstimate?.toLocaleString() ?? '---'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="space-y-6">
          {/* Terminal */}
          <Terminal />

          {/* Outreach History Log */}
          <div className="bg-slate-800 border border-slate-700 rounded-lg shadow-lg overflow-hidden flex flex-col h-96">
            <div className="px-6 py-4 border-b border-slate-700">
              <h3 className="text-lg font-semibold text-white">Outreach Log</h3>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {outreachHistory.length === 0 ? (
                <div className="text-center text-slate-500 py-8">No messages sent yet.</div>
              ) : (
                outreachHistory.map((log) => (
                  <div key={log.id} className="bg-slate-900/50 p-3 rounded border border-slate-700 text-xs">
                    <div className="flex justify-between text-slate-400 mb-1">
                      <span>{new Date(log.sentAt).toLocaleTimeString()}</span>
                      <span className={log.status === 'Sent' ? 'text-emerald-500' : 'text-red-500'}>{log.status}</span>
                    </div>
                    <div className="font-medium text-white mb-1">{log.recipientEmail}</div>
                    <div className="text-slate-500 truncate">{log.address}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;