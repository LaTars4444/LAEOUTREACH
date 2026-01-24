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

# Global Production Memory Log Buffer
SYSTEM_LOGS = []

def log_activity(message):
    """
    INDUSTRIAL LOGGING ENGINE.
    SURGICAL FIX: Uses Manual Explicit Indexing {0} to prevent Render crashes.
    """
    try:
        timestamp = time.strftime("%H:%M:%S")
        log_template = "[{0}] {1}"
        entry = log_template.format(timestamp, message)
        print(entry)
        SYSTEM_LOGS.insert(0, entry)
        if len(SYSTEM_LOGS) > 5000: SYSTEM_LOGS.pop()
    except: pass

def vicious_hunter(app, user_id, city, state, api_key, cx):
    """
    ENTERPRISE SCRAPER CORE.
    Optimized for searching across a massive 1,000-site Google CX Network.
    Logic: Combinatorial search query generation with deep pagination loops.
    """
    with app.app_context():
        start_log = "🚀 MISSION STARTED: Hunting leads in {0}, {1}".format(city, state)
        log_activity(start_log)
        try:
            service = build("customsearch", "v1", developerKey=api_key)
            keywords = ["must sell", "cash buyer", "motivated seller", "probate deal", "divorce sale", "fixer upper"]
            total_added = 0
            
            # Combinatorial Query Rotation
            for kw in keywords:
                # INDUSTRIAL PAGINATION: 10 pages per combinatorial (100 leads per keyword)
                for start in range(1, 101, 10):
                    query_template = '"{0}" "{1}" {2}'
                    q = query_template.format(city, state, kw)
                    
                    response = service.cse().list(q=q, cx=cx, num=10, start=start).execute()
                    if 'items' not in response: break

                    for item in response.get('items', []):
                        snippet = (item.get('snippet', '') + " " + item.get('title', '')).lower()
                        link = item.get('link', '#')
                        
                        # INDUSTRIAL REGEX DATA EXTRACTION PIPELINE
                        phones = re.findall(r'\(?\d{}\)?[-.\s]?\d{}[-.\s]?\d{}', snippet)
                        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', snippet)
                        
                        if phones or emails:
                            if not Lead.query.filter_by(link=link, submitter_id=user_id).first():
                                # Owner Identification Heuristics
                                owner_label = "Property Owner"
                                name_check = re.search(r'by\s+([a-zA-Z]+)', snippet)
                                if name_check: owner_label = name_check.group(1).capitalize()

                                industrial_lead = Lead(
                                    submitter_id=user_id,
                                    address=item.get('title')[:100],
                                    name=owner_label,
                                    phone=phones[0] if phones else "None",
                                    email=emails[0] if emails else "None",
                                    source="Enterprise Network",
                                    link=link
                                )
                                db.session.add(industrial_lead)
                                total_added += 1
                                harvest_log = "✅ HARVESTED: {0}".format(industrial_lead.address[:25])
                                log_activity(harvest_log)
                    
                    db.session.commit()
                    human_stealth_delay() # Mandatory behavioral jitter
            
            final_log = "🏁 MISSION COMPLETE: {0} leads indexed.".format(total_added)
            log_activity(final_log)
        except Exception as e:
            log_activity("⚠️ SCRAPE FAULT: {0}".format(str(e)))

def outreach_machine(app, user_id, subject, body, groq_client):
    """
    INDUSTRIAL OUTREACH MACHINE.
    Functional logic for Universal scripts and Dynamic Property Injection.
    """
    with app.app_context():
        user = User.query.get(user_id)
        leads = Lead.query.filter(Lead.submitter_id == user_id, Lead.email.contains('@')).all()
        log_activity("📧 BLAST STARTING: Targeting {0} potential sellers.".format(len(leads)))
        
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(user.smtp_email, user.smtp_password)
            
            for lead in leads:
                try:
                    # DYNAMIC UNIVERSAL SCRIPT INJECTION
                    # Logic swaps industrial tags [[ADDRESS]] and [[NAME]] with real-time database values
                    final_msg = body if body and len(body) > 10 else user.email_template
                    final_msg = final_msg.replace("[[ADDRESS]]", lead.address)
                    final_msg = final_msg.replace("[[NAME]]", lead.name)
                    
                    # AI SMART OVERRIDE (GROQ LLAMA 3.3)
                    if groq_client and len(final_msg) < 15:
                        chat = groq_client.chat.completions.create(
                            messages=[{"role": "user", "content": "Write a short cash buyer email for {0}.".format(lead.address)}],
                            model="llama-3.3-70b-versatile"
                        )
                        final_msg = chat.choices[0].message.content

                    msg = MIMEMultipart()
                    msg['From'] = user.smtp_email
                    msg['To'] = lead.email
                    msg['Subject'] = subject.replace("[[ADDRESS]]", lead.address)
                    msg.attach(MIMEText(final_msg, 'plain'))
                    
                    server.send_message(msg)
                    
                    # PERSISTENT HISTORY LOGGING (Solves 500 error)
                    # We ensure the address is logged for visibility pane.
                    outlog = OutreachLog(user_id=user_id, recipient_email=lead.email, address=lead.address, message=final_msg[:250])
                    db.session.add(outlog)
                    lead.emailed_count += 1; lead.status = "Contacted"; db.session.commit()
                    
                    log_activity("📨 SENT: {0}".format(lead.email))
                    human_stealth_delay()
                except Exception as e:
                    log_activity("⚠️ SMTP FAIL ({0}): {1}".format(lead.email, str(e)))
            
            server.quit()
            log_activity("🏁 BLAST MISSION COMPLETE.")
        except Exception as e:
            log_activity("❌ SMTP CRITICAL ERROR: {0}".format(str(e)))
