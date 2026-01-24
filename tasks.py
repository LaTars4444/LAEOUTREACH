
import os
import random
import re
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from extensions import db
from models import Lead, OutreachLog, User
from utils import human_stealth_delay

# Production Log Buffer
SYSTEM_LOGS = []

def log_activity(message):
    """ Surgical Indexed Formatting to prevent Render crashes. """
    try:
        timestamp = time.strftime("%H:%M:%S")
        log_format = "[{0}] {1}"
        entry = log_format.format(timestamp, message)
        print(entry)
        SYSTEM_LOGS.insert(0, entry)
        if len(SYSTEM_LOGS) > 3000: SYSTEM_LOGS.pop()
    except: pass

def task_scraper(app, user_id, city, state, api_key, cx):
    """
    INDUSTRIAL LEAD HUNTER.
    Optimized for 1,000+ Site CX Clusters.
    """
    with app.app_context():
        log_activity("🚀 MISSION STARTED: Lead Extraction in {0}, {1}".format(city, state))
        try:
            service = build("customsearch", "v1", developerKey=api_key)
            keywords = ["must sell", "motivated seller", "cash only", "inherited property", "probate", "divorce"]
            total_added = 0
            
            for kw in keywords:
                for start in range(1, 101, 10): # 100 deep results per combinatorial
                    query_format = '"{0}" "{1}" {2}'
                    q = query_format.format(city, state, kw)
                    
                    res = service.cse().list(q=q, cx=cx, num=10, start=start).execute()
                    if 'items' not in res: break

                    for item in res.get('items', []):
                        snippet = (item.get('snippet', '') + " " + item.get('title', '')).lower()
                        link = item.get('link', '#')
                        
                        phones = re.findall(r'\(?\d{}\)?[-.\s]?\d{}[-.\s]?\d{}', snippet)
                        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', snippet)
                        
                        if phones or emails:
                            if not Lead.query.filter_by(link=link, submitter_id=user_id).first():
                                # Property Name Heuristic
                                owner_name = "Property Owner"
                                name_find = re.search(r'by\s+([a-zA-Z]+)', snippet)
                                if name_find: owner_name = name_find.group(1).capitalize()

                                lead = Lead(
                                    submitter_id=user_id,
                                    address=item.get('title')[:100],
                                    name=owner_name,
                                    phone=phones[0] if phones else "None",
                                    email=emails[0] if emails else "None",
                                    source="Industrial Network",
                                    link=link
                                )
                                db.session.add(lead)
                                total_added += 1
                                log_activity("✅ HARVESTED: {0}".format(lead.address[:25]))
                    
                    db.session.commit()
                    human_stealth_delay() 
            
            log_activity("🏁 MISSION COMPLETE: indexed {0} leads.".format(total_added))
        except Exception as e:
            log_activity("⚠️ SCRAPE FAULT: {0}".format(str(e)))

def task_emailer(app, user_id, subject, body, groq_client):
    """ INDUSTRIAL OUTREACH MACHINE - UNIVERSAL SCRIPT LOGIC """
    with app.app_context():
        user = User.query.get(user_id)
        leads = Lead.query.filter(Lead.submitter_id == user_id, Lead.email.contains('@')).all()
        log_activity("📧 BLAST STARTING: Targeting {0} leads.".format(len(leads)))
        
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls(); server.login(user.smtp_email, user.smtp_password)
            
            for lead in leads:
                try:
                    # Dynamic Injection logic
                    msg_body = body if body and len(body) > 10 else user.email_template
                    msg_body = msg_body.replace("[[ADDRESS]]", lead.address).replace("[[NAME]]", lead.name)
                    
                    # AI personalization override via Groq
                    if groq_client and len(msg_body) < 15:
                        chat = groq_client.chat.completions.create(
                            messages=[{"role": "user", "content": "Write a short cash buyer email for {0}.".format(lead.address)}],
                            model="llama-3.3-70b-versatile"
                        )
                        msg_body = chat.choices[0].message.content

                    msg = MIMEMultipart(); msg['From'] = user.smtp_email; msg['To'] = lead.email; msg['Subject'] = subject.replace("[[ADDRESS]]", lead.address)
                    msg.attach(MIMEText(msg_body, 'plain')); server.send_message(msg)
                    
                    # Log History
                    out = OutreachLog(user_id=user_id, recipient_email=lead.email, address=lead.address, message=msg_body[:250])
                    db.session.add(out); lead.emailed_count += 1; lead.status = "Contacted"; db.session.commit()
                    
                    log_activity("📨 SENT: {0}".format(lead.email))
                    human_stealth_delay()
                except Exception as e:
                    log_activity("⚠️ SMTP FAIL ({0}): {1}".format(lead.email, str(e)))
            server.quit(); log_activity("🏁 BLAST COMPLETE.")
        except Exception as e:
            log_activity("❌ SMTP CRITICAL ERROR: {0}".format(str(e)))
