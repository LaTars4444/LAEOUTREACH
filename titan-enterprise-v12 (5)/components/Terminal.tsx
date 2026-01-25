import React from 'react';
import { useStore } from '../context/Store';
import { Terminal as TerminalIcon, Activity } from 'lucide-react';

const Terminal: React.FC = () => {
  const { logs } = useStore();

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg shadow-2xl overflow-hidden flex flex-col h-64 md:h-80">
      <div className="bg-slate-800 px-4 py-2 flex items-center justify-between border-b border-slate-700">
        <div className="flex items-center gap-2 text-slate-300">
          <TerminalIcon size={16} />
          <span className="text-xs font-mono font-bold tracking-wider">TITAN_KERNEL_V12.0.0</span>
        </div>
        <div className="flex items-center gap-2">
          <Activity size={14} className="text-emerald-500 animate-pulse" />
          <span className="text-[10px] text-emerald-500 font-mono">ONLINE</span>
        </div>
      </div>
      <div className="flex-1 p-4 overflow-y-auto terminal-scroll font-mono text-xs md:text-sm bg-black/50">
        {logs.length === 0 && (
          <div className="text-slate-500 italic">System ready. Awaiting commands...</div>
        )}
        {logs.map((log) => (
          <div key={log.id} className="mb-1 break-words">
            <span className="text-slate-500 mr-2">[{log.timestamp}]</span>
            <span className={`
              ${log.type === 'error' ? 'text-red-500 font-bold' : ''}
              ${log.type === 'warning' ? 'text-amber-400' : ''}
              ${log.type === 'success' ? 'text-emerald-400' : ''}
              ${log.type === 'info' ? 'text-slate-300' : ''}
            `}>
              {log.message}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Terminal;