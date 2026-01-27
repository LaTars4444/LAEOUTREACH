export interface User {
  id: number;
  email: string;
  subscriptionStatus: 'free' | 'weekly' | 'monthly' | 'lifetime';
  emailTemplate: string;
  smtpEmail?: string;
  smtpPassword?: string;
  groqApiKey?: string; // For the AI Terminal
  
  // Feature Access Flags
  hasEmailAccess: boolean;
  hasAiAccess: boolean;
  isAdmin: boolean;
  trialStart?: string | null; // ISO Date string, null if not started

  // Buy Box Criteria (Operator's)
  bbLocations?: string;
  bbMinPrice?: number;
  bbMaxPrice?: number;
  bbPropertyType?: string;
  bbCondition?: string;
  bbStrategy?: string;
}

export interface Lead {
  id: number;
  address: string;
  name: string;
  phone: string;
  email: string;
  status: 'New' | 'Contacted' | 'Hot' | 'Dead';
  source: string;
  emailedCount: number;
  createdAt: string;
  arvEstimate?: number;
  repairEstimate?: number;
  askingPrice?: number;
}

export interface Investor {
  id: number;
  name: string;
  email: string;
  phone: string;
  markets: string;
  minPrice: number;
  maxPrice: number;
  assetClass: string;
  strategy: string;
  createdAt: string;
}

export interface OutreachLog {
  id: number;
  recipientEmail: string;
  address: string;
  message: string;
  sentAt: string;
  status: 'Sent' | 'Failed';
}

export interface SystemLog {
  id: string;
  timestamp: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
}

export const DEFAULT_TEMPLATE = "Hi [[NAME]], I am a local cash investor interested in your property at [[ADDRESS]]. Can we discuss an offer?";
