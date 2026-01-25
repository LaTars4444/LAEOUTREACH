import React from 'react';
import { HashRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { StoreProvider, useStore } from './context/Store';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import Hunter from './pages/Hunter';
import Campaigns from './pages/Campaigns';
import Settings from './pages/Settings';
import Login from './pages/Login';
import BuyBox from './pages/BuyBox';
import Sell from './pages/Sell';
import JoinBuyersList from './pages/JoinBuyersList';
import Paywall from './pages/Paywall';
import AiTerminal from './pages/AiTerminal';

const AppLayout: React.FC = () => {
  const { isAuthenticated } = useStore();

  // Public Routes (Login, Sell, Join Buyers List)
  if (!isAuthenticated) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/sell" element={<Sell />} />
        <Route path="/investors" element={<JoinBuyersList />} />
        <Route path="*" element={<Navigate to="/login" />} />
      </Routes>
    );
  }

  // Authenticated Routes
  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-200 font-sans">
      <Sidebar />
      <main className="flex-1 ml-64 p-8 overflow-y-auto h-screen">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/hunter" element={<Hunter />} />
          <Route path="/ai-terminal" element={<AiTerminal />} />
          <Route path="/buy-box" element={<BuyBox />} />
          <Route path="/campaigns" element={<Campaigns />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/sell" element={<Sell />} />
          <Route path="/investors" element={<JoinBuyersList />} />
          <Route path="/paywall" element={<Paywall />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </div>
  );
};

const App: React.FC = () => {
  return (
    <StoreProvider>
      <Router>
        <AppLayout />
      </Router>
    </StoreProvider>
  );
};

export default App;