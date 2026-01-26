import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Crosshair, Send, Settings, LogOut, ShieldCheck, BoxSelect, Lock, Cpu } from 'lucide-react';
import { useStore } from '../context/Store';

const Sidebar: React.FC = () => {
  const { logout, user } = useStore();

  const navItems = [
    { to: '/', icon: LayoutDashboard, label: 'Dashboard', locked: false },
    { to: '/hunter', icon: Crosshair, label: 'Lead Hunter', locked: !user?.hasAiAccess },
    { to: '/ai-terminal', icon: Cpu, label: 'AI Terminal', locked: !user?.hasAiAccess },
    { to: '/buy-box', icon: BoxSelect, label: 'Buy Box', locked: false },
    { to: '/campaigns', icon: Send, label: 'Outreach', locked: !user?.hasEmailAccess },
    { to: '/settings', icon: Settings, label: 'Settings', locked: false },
  ];

  return (
    <div className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col h-screen fixed left-0 top-0 z-10">
      <div className="p-6 border-b border-slate-800">
        <div className="flex items-center gap-2 text-emerald-500 mb-1">
          <ShieldCheck size={24} />
          <h1 className="text-xl font-bold tracking-tight text-white">TITAN <span className="text-slate-500 text-sm font-normal">ENT</span></h1>
        </div>
        <div className="text-[10px] text-slate-500 font-mono">V12.0.0 INDUSTRIAL BUILD</div>
      </div>

      <nav className="flex-1 p-4 space-y-2">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex items-center justify-between px-4 py-3 rounded-md transition-all duration-200 ${
                isActive
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
              }`
            }
          >
            <div className="flex items-center gap-3">
              <item.icon size={18} />
              <span className="font-medium">{item.label}</span>
            </div>
            {item.locked && <Lock size={14} className="text-slate-600" />}
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-slate-800">
        <div className="mb-4 px-2">
          <div className="text-xs text-slate-500 uppercase mb-1">Operator</div>
          <div className="text-sm text-white truncate">{user?.email}</div>
          <div className="text-[10px] text-emerald-500 mt-1 flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            {user?.isAdmin ? 'ADMIN ACCESS' : 'SECURE CONNECTION'}
          </div>
        </div>
        <button
          onClick={logout}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-slate-800 hover:bg-red-900/20 hover:text-red-400 text-slate-400 rounded-md transition-colors text-sm"
        >
          <LogOut size={16} />
          Disconnect
        </button>
      </div>
    </div>
  );
};

export default Sidebar;