import os
import requests
from extensions import db
from models import Lead, OutreachLog
from utils import human_stealth_delay

def google_search_hunter(app, user_id, city, state, api_key, cx):
    """
    Performs real Google Custom Search API queries.
    """
    with app.app_context():
        queries = [
            f'site:zillow.com "for sale by owner" {city} {state}',
            f'site:craigslist.org "fixer upper" {city} {state}',
            f'"motivated seller" {city} {state} real estate'
        ]
        
        count = 0
        for q in queries:
            try:
                url = f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={cx}&q={q}"
                res = requests.get(url)
                data = res.json()
                
                if 'items' in data:
                    for item in data['items']:
                        # Basic deduplication
                        if not Lead.query.filter_by(address=item['title']).first():
                            lead = Lead(
                                submitter_id=user_id,
                                address=item['title'],
                                source="Google API",
                                link=item['link']
                            )
                            db.session.add(lead)
                            count += 1
                human_stealth_delay()
            except Exception as e:
                print(f"Search Error: {e}")
        
        db.session.commit()
        print(f"Harvested {count} leads.")
