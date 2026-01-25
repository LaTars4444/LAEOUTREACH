export const USA_STATES: Record<string, string[]> = {
  "AL": ["Birmingham", "Montgomery", "Mobile", "Huntsville"],
  "AK": ["Anchorage", "Juneau", "Fairbanks"],
  "AZ": ["Phoenix", "Tucson", "Mesa", "Scottsdale"],
  "CA": ["Los Angeles", "San Diego", "San Francisco", "Sacramento", "Fresno"],
  "CO": ["Denver", "Colorado Springs", "Aurora"],
  "FL": ["Miami", "Tampa", "Orlando", "Jacksonville"],
  "GA": ["Atlanta", "Savannah", "Augusta"],
  "IL": ["Chicago", "Aurora", "Rockford"],
  "NY": ["New York City", "Buffalo", "Rochester"],
  "TX": ["Houston", "Dallas", "Austin", "San Antonio"],
  "WA": ["Seattle", "Spokane", "Tacoma"]
};

export const MOCK_LEADS_START: any[] = [
  {
    id: 101,
    address: "123 Maple Ave, Springfield, IL",
    name: "John Doe",
    phone: "(555) 123-4567",
    email: "jdoe@example.com",
    status: "New",
    source: "Enterprise Network",
    emailedCount: 0,
    createdAt: new Date().toISOString(),
    arvEstimate: 250000,
    repairEstimate: 40000
  },
  {
    id: 102,
    address: "456 Oak St, Austin, TX",
    name: "Jane Smith",
    phone: "(555) 987-6543",
    email: "jane.smith@test.com",
    status: "Contacted",
    source: "Network Extraction",
    emailedCount: 1,
    createdAt: new Date(Date.now() - 86400000).toISOString(),
    arvEstimate: 450000,
    repairEstimate: 15000
  }
];