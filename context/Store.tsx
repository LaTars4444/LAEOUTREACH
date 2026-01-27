import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { User, Lead, OutreachLog, SystemLog, Investor, DEFAULT_TEMPLATE } from '../utils/types';
import { MOCK_LEADS_START } from '../utils/constants';

interface StoreContextType {
  user: User | null;
  leads: Lead[];
  investors: Investor[];
  logs: SystemLog[];
  outreachHistory: OutreachLog[];
  isAuthenticated: boolean;
  login: (email: string) => void;
  register: (email: string) => void;
  logout: () => void;
  addLog: (message: string, type?: 'info' | 'success' | 'warning' | 'error') => void;
  addLead: (lead: Lead) => void;
  addInvestor: (investor: Investor) => void;
  updateUser: (updates: Partial<User>) => void;
  recordOutreach: (log: OutreachLog) => void;
  purchasePlan: (plan: 'weekly_email' | 'lifetime_email' | 'monthly_ai') => void;
  cancelSubscription: () => void;
  activateTrial: () => void;
  checkTrial: () => boolean;
}

const StoreContext = createContext<StoreContextType | undefined>(undefined);

const ADMIN_EMAILS = ['leewaits836@gmail.com', 'emyr.jones.0@outlook.com'];

export const StoreProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Simulate persistent storage
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem('titan_user');
    return saved ? JSON.parse(saved) : null;
  });

  const [leads, setLeads] = useState<Lead[]>(() => {
    const saved = localStorage.getItem('titan_leads');
    return saved ? JSON.parse(saved) : MOCK_LEADS_START;
  });

  const [investors, setInvestors] = useState<Investor[]>(() => {
    const saved = localStorage.getItem('titan_investors');
    return saved ? JSON.parse(saved) : [];
  });

  const [outreachHistory, setOutreachHistory] = useState<OutreachLog[]>(() => {
    const saved = localStorage.getItem('titan_history');
    return saved ? JSON.parse(saved) : [];
  });

  const [logs, setLogs] = useState<SystemLog[]>([]);

  // Persistence Effects
  useEffect(() => {
    if (user) localStorage.setItem('titan_user', JSON.stringify(user));
    else localStorage.removeItem('titan_user');
  }, [user]);

  useEffect(() => {
    localStorage.setItem('titan_leads', JSON.stringify(leads));
  }, [leads]);

  useEffect(() => {
    localStorage.setItem('titan_investors', JSON.stringify(investors));
  }, [investors]);

  useEffect(() => {
    localStorage.setItem('titan_history', JSON.stringify(outreachHistory));
  }, [outreachHistory]);

  const addLog = useCallback((message: string, type: 'info' | 'success' | 'warning' | 'error' = 'info') => {
    const newLog: SystemLog = {
      id: Math.random().toString(36).substr(2, 9),
      timestamp: new Date().toLocaleTimeString(),
      message,
      type
    };
    setLogs(prev => [newLog, ...prev].slice(0, 100)); // Keep last 100 logs
  }, []);

  // --- TRIAL VALIDATION LOGIC ---
  const validateTrialStatus = useCallback((currentUser: User): User => {
    // Admins and Paid users are always valid
    if (currentUser.isAdmin || currentUser.subscriptionStatus !== 'free') {
      return { ...currentUser, hasEmailAccess: true, hasAiAccess: true };
    }

    // If trial hasn't started yet, they have no access (Forces them to Paywall to activate)
    if (!currentUser.trialStart) {
      return { ...currentUser, hasEmailAccess: false, hasAiAccess: false };
    }

    const now = new Date().getTime();
    const start = new Date(currentUser.trialStart).getTime();
    const hoursElapsed = (now - start) / (1000 * 60 * 60);

    if (hoursElapsed > 48) {
      // Expire Trial
      if (currentUser.hasEmailAccess || currentUser.hasAiAccess) {
        addLog("⚠️ TRIAL EXPIRED: Access revoked. Please upgrade.", "warning");
        return { ...currentUser, hasEmailAccess: false, hasAiAccess: false };
      }
    } else {
      // Active Trial
      return { ...currentUser, hasEmailAccess: true, hasAiAccess: true };
    }
    return currentUser;
  }, [addLog]);

  // Check trial on mount/refresh - ONLY if user is logged in
  useEffect(() => {
    if (user) {
      const validatedUser = validateTrialStatus(user);
      if (JSON.stringify(validatedUser) !== JSON.stringify(user)) {
        setUser(validatedUser);
      }
    }
  }, []); // Run once on mount

  const createNewUser = (email: string, isAdmin: boolean): User => ({
    id: Date.now(),
    email,
    subscriptionStatus: isAdmin ? 'lifetime' : 'free',
    emailTemplate: DEFAULT_TEMPLATE,
    hasEmailAccess: isAdmin, // False for new users until trial activation
    hasAiAccess: isAdmin,    // False for new users until trial activation
    isAdmin: isAdmin,
    trialStart: null,        // Null = Trial not started
    groqApiKey: '' 
  });

  const login = (email: string) => {
    const isAdmin = ADMIN_EMAILS.includes(email.toLowerCase());
    
    const existingUserStr = localStorage.getItem('titan_user');
    let userData: User;

    if (existingUserStr) {
      const existing = JSON.parse(existingUserStr);
      if (existing.email === email) {
        userData = { ...existing, isAdmin };
      } else {
        userData = createNewUser(email, isAdmin);
      }
    } else {
      userData = createNewUser(email, isAdmin);
    }

    // Validate Trial immediately on login
    userData = validateTrialStatus(userData);

    setUser(userData);
    addLog(`User ${email} authenticated via Industrial Gateway.`);
    if (isAdmin) {
      addLog(`👑 ADMIN ACCESS GRANTED: Infinite System Privileges.`, 'success');
    }
  };

  const register = (email: string) => {
    const isAdmin = ADMIN_EMAILS.includes(email.toLowerCase());
    const newUser = createNewUser(email, isAdmin);
    setUser(newUser);
    addLog(`New Operator Registered: ${email}`, 'success');
    if (isAdmin) {
      addLog(`👑 ADMIN RECOGNIZED: Privileges Auto-Granted.`, 'success');
    } else {
      addLog(`⚠️ ACCOUNT CREATED: Please activate your trial in the dashboard.`, 'warning');
    }
  };

  const logout = () => {
    setUser(null);
    addLog('Session terminated.');
  };

  const addLead = (lead: Lead) => {
    setLeads(prev => [lead, ...prev]);
  };

  const addInvestor = (investor: Investor) => {
    setInvestors(prev => [investor, ...prev]);
  };

  const updateUser = (updates: Partial<User>) => {
    setUser((prev: User | null) => prev ? { ...prev, ...updates } : null);
  };

  const recordOutreach = (log: OutreachLog) => {
    setOutreachHistory(prev => [log, ...prev]);
    setLeads(prev => prev.map(l => {
      if (l.email === log.recipientEmail) {
        return { ...l, status: 'Contacted', emailedCount: l.emailedCount + 1 };
      }
      return l;
    }));
  };

  const purchasePlan = (plan: 'weekly_email' | 'lifetime_email' | 'monthly_ai') => {
    if (!user) return;
    
    let updates: Partial<User> = {};
    
    if (plan === 'weekly_email') {
      updates = { hasEmailAccess: true, subscriptionStatus: 'weekly' };
      addLog("💳 PAYMENT SUCCESS: Weekly Email Access Activated.", "success");
    } else if (plan === 'lifetime_email') {
      updates = { hasEmailAccess: true, subscriptionStatus: 'lifetime' };
      addLog("💳 PAYMENT SUCCESS: Lifetime Email Access Activated.", "success");
    } else if (plan === 'monthly_ai') {
      // AI Plan includes EVERYTHING
      updates = { hasAiAccess: true, hasEmailAccess: true, subscriptionStatus: 'monthly' };
      addLog("💳 PAYMENT SUCCESS: AI & Lead Finder Module Activated (Includes Email Machine).", "success");
    }

    updateUser(updates);
  };

  const activateTrial = () => {
    if (!user) return;
    if (user.trialStart) return; // Already started

    const updates: Partial<User> = {
      trialStart: new Date().toISOString(),
      hasEmailAccess: true,
      hasAiAccess: true
    };
    updateUser(updates);
    addLog("⏳ 48-HOUR TRIAL ACTIVATED: Full System Access Granted.", "success");
  };

  const cancelSubscription = () => {
    if (!user) return;
    
    // Revert to free
    const downgradedUser: User = { ...user, subscriptionStatus: 'free' };
    
    // Check if they still have trial time left
    const validatedUser = validateTrialStatus(downgradedUser);
    
    setUser(validatedUser);
    addLog("⚠️ SUBSCRIPTION CANCELLED: Reverted to Free Tier.", "warning");
  };

  const checkTrial = () => {
    if (!user) return false;
    if (user.isAdmin || user.subscriptionStatus !== 'free') return true;
    if (!user.trialStart) return false; // Not started yet
    const now = new Date().getTime();
    const start = new Date(user.trialStart).getTime();
    return (now - start) < (48 * 60 * 60 * 1000);
  };

  return (
    <StoreContext.Provider value={{
      user,
      leads,
      investors,
      logs,
      outreachHistory,
      isAuthenticated: !!user,
      login,
      register,
      logout,
      addLog,
      addLead,
      addInvestor,
      updateUser,
      recordOutreach,
      purchasePlan,
      cancelSubscription,
      activateTrial,
      checkTrial
    }}>
      {children}
    </StoreContext.Provider>
  );
};

export const useStore = () => {
  const context = useContext(StoreContext);
  if (!context) throw new Error("useStore must be used within StoreProvider");
  return context;
};
