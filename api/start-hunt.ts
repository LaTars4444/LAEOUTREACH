import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const { state, city, linkepyEnabled } = req.body;

  if (!state || !city) {
    return res.status(400).json({ error: 'Missing city or state' });
  }

  const ATTOM_API_KEY = process.env.ATTOM_API_KEY;

  if (!ATTOM_API_KEY) {
    return res.status(500).json({ error: 'ATTOM API Key not configured' });
  }

  let leadsAdded = 0;

  try {
    // --- 1) Fetch properties from ATTOM ---
    const attomUrl = `https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/address?state=${state}&city=${city}&pageSize=50`;
    const attomRes = await fetch(attomUrl, {
      headers: { 'apikey': ATTOM_API_KEY }
    });
    const attomData = await attomRes.json();

    const leads = [];

    for (const prop of attomData.properties || []) {
      const ownerName = prop.owner?.name || "Property Owner";
      let email = null;
      let phone = null;

      // --- 2) Optional Linkepy enrichment ---
      if (linkepyEnabled) {
        try {
          const enrichRes = await fetch('https://api.linkepy.com/api/enrichment/email-lookup', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${process.env.LINKEPY_API_KEY}`,
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
        } catch (err) {
          console.warn('Linkepy enrichment failed', err);
        }
      }

      // --- 3) Build lead object ---
      const newLead = {
        id: Date.now() + Math.random(),
        address: prop.address?.line1 || "Unknown Address",
        name: ownerName,
        email,
        phone,
        status: 'New',
        source: 'ATTOM',
        createdAt: new Date().toISOString(),
      };

      leads.push(newLead);
      leadsAdded++;

      // TODO: Save to your database/dashboard
      // Example: await saveLeadToDashboard(newLead)
    }

    res.status(200).json({ message: 'Leads harvested', leadsAdded });
  } catch (err: any) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
}
