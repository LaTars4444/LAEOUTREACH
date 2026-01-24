import os
import random
import time
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from googleapiclient.discovery import build
from extensions import db
from models import Lead, OutreachLog, User

# GLOBAL LOG BUFFER
SYSTEM_LOGS = []

def log_activity(message):
    """
    Industrial Standard Logger.
    SURGICAL FIX: Uses indexed format to prevent Render crash.
    """
    try:
        timestamp = time.strftime("%H:%M:%S")
        log_format = "[{0}] {1}"
        entry = log_format.format(timestamp, message)
        print(entry)
        SYSTEM_LOGS.insert(0, entry)
        if len(SYSTEM_LOGS) > 2000: SYSTEM_LOGS.pop()
    except:
        pass

def task_scraper(app, user_id, city, state, api_key, cx, keywords):
    """
    ENGINE: INDUSTRIAL LEAD HUNTER.
    - Optimized for 1,000+ site CX Network.
    - Deep Pagination (start=1-100).
    - Randomized stealth delays (5-15s).
    """
    with app.app_context():
        log_activity("🚀 MISSION STARTED: Lead Extraction in {0}, {1}".format(city, state))
        
        try:
            service = build("customsearch", "v1", developerKey=api_key)
            total_added = 0
            selected_kws = random.sample(keywords, 15)
            
            for kw in selected_kws:
                for start in range(1, 101, 10):
                    # ENTERPRISE CX NETWORK QUERY
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
                                # Property Name Extraction
                                owner_name = "Property Owner"
                                name_match = re.search(r'by\s+([a-zA-Z]+)', snippet)
                                if name_match: owner_name = name_match.group(1).capitalize()

                                lead = Lead(
                                    submitter_id=user_id,
                                    address=item.get('title')[:100],
                                    name=owner_name,
                                    phone=phones[0] if phones else "None",
                                    email=emails[0] if emails else "None",
                                    source="Network ({0})".format(kw),
                                    link=link
                                )
                                db.session.add(lead)
                                total_added += 1
                                log_activity("✅ HARVESTED: {0}".format(lead.address[:25]))
                    
                    db.session.commit()
                    time.sleep(random.uniform(5, 15)) # STEALTH DELAY
            
            log_activity("🏁 MISSION COMPLETE: indexed {0} Leads.".format(total_added))
        except Exception as e:
            log_activity("⚠️ SCRAPE FAULT: {0}".format(str(e)))

def task_emailer(app, user_id, subject, body, groq_client):
    """
    ENGINE: OUTREACH AUTOMATION MACHINE.
    - Constant Universal Script Injection ([[ADDRESS]], [[NAME]]).
    - Historical SENT history logging.
    - Human stealth delays (5-15s).
    """
    with app.app_context():
        user = User.query.get(user_id)
        leads = Lead.query.filter(Lead.submitter_id == user_id, Lead.email.contains('@')).all()
        log_activity("📧 BLAST STARTING: Targeting {0} leads.".format(len(leads)))
        
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(user.smtp_email, user.smtp_password)
            
            count = 0
            for lead in leads:
                try:
                    final_body = body if body and len(body) > 10 else user.email_template
                    final_body = final_body.replace("[[ADDRESS]]", lead.address)
                    final_body = final_body.replace("[[NAME]]", lead.name)
                    
                    if groq_client and len(final_body) < 15:
                        chat = groq_client.chat.completions.create(
                            messages=[{"role": "user", "content": "Write a short cash offer for {0}.".format(lead.address)}],
                            model="llama-3.3-70b-versatile"
                        )
                        final_body = chat.choices[0].message.content

                    msg = MIMEMultipart()
                    msg['From'] = user.smtp_email
                    msg['To'] = lead.email
                    msg['Subject'] = subject.replace("[[ADDRESS]]", lead.address)
                    msg.attach(MIMEText(final_body, 'plain'))
                    
                    server.send_message(msg)
                    
                    # LOG HISTORY
                    outlog = OutreachLog(user_id=user_id, address=lead.address, recipient_email=lead.email, message=final_body[:200], status="Sent")
                    db.session.add(outlog)
                    lead.emailed_count += 1; lead.status = "Contacted"; db.session.commit()
                    
                    count += 1
                    log_activity("📨 SENT: {0}".format(lead.email))
                    time.sleep(random.uniform(5, 15)) # ANTI-SPAM
                except Exception as e:
                    log_activity("⚠️ SMTP FAIL ({0}): {1}".format(lead.email, str(e)))
            
            server.quit()
            log_activity("🏁 BLAST COMPLETE: {0} Delivered.".format(count))
        except Exception as e:
            log_activity("❌ SMTP CRITICAL ERROR: {0}".format(str(e)))
