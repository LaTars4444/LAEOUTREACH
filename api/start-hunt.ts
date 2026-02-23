export async function startHunt(req: any, res: any) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method Not Allowed' });

  const { state, city, linkepyEnabled } = req.body;
  if (!state || !city) return res.status(400).json({ error: 'Missing city or state' });

  const ATTOM_API_KEY = process.env.ATTOM_API_KEY;
  const LINKEPY_API_KEY = process.env.LINKEPY_API_KEY;
  if (!ATTOM_API_KEY) return res.status(500).json({ error: 'ATTOM API key missing' });

  let leads: any[] = [];

  try {
    // Use global fetch (Node 18+)
    const attomRes = await fetch(
      `https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/address?state=${state}&city=${city}&pageSize=50`,
      { headers: { apikey: ATTOM_API_KEY } }
    );
    const attomData = await attomRes.json();

    for (const prop of attomData.properties || []) {
      const ownerName = prop.owner?.name || "Property Owner";
      let email: string | null = null;
      let phone: string | null = null;

      if (linkepyEnabled && LINKEPY_API_KEY) {
        try {
          const enrichRes = await fetch('https://api.linkepy.com/api/enrichment/email-lookup', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${LINKEPY_API_KEY}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              firstName: ownerName.split(' ')[0],
              lastName: ownerName.split(' ')[1] || '',
              location: `${city}, ${state}`
            })
          });
          const enrichData = await enrichRes.json();
          email = enrichData?.email || null;
          phone = enrichData?.phone || null;
        } catch {}
      }

      leads.push({
        id: Date.now() + Math.random(),
        address: prop.address?.line1 || "Unknown Address",
        name: ownerName,
        email,
        phone,
        status: 'New',
        source: 'ATTOM',
        createdAt: new Date().toISOString()
      });
    }

    res.status(200).json({ leadsAdded: leads.length, leads });
  } catch (err: any) {
    res.status(500).json({ error: err.message || 'Server error' });
  }
}
🔹 TypeScript Fix

TypeScript in Node 20+ sometimes doesn’t know fetch exists. Add this to your tsconfig.json:

{
  "compilerOptions": {
    "lib": ["ESNext", "DOM"], // include DOM lib for fetch types
    "module": "ESNext",
    "target": "ES2022",
    "moduleResolution": "Node",
    "strict": true,
    "esModuleInterop": true
  }
}
