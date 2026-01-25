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

SYSTEM_LOGS = []

def log_activity(message):
    """ Surgical Indexed Formatting logic. """
    try:
        timestamp = time.strftime("%H:%M:%S")
        log_format = "[{0}] {1}"
        entry = log_format.format(timestamp, message)
        print(entry)
        SYSTEM_LOGS.insert(0, entry)
        if len(SYSTEM_LOGS) > 5000: SYSTEM_LOGS.pop()
    except: pass

def industrial_hunter(app, user_id, city, state, api_key, cx):
    """ Lead harvesting engine for 1,000+ site networks. """
    with app.app_context():
        log_activity("🚀 MISSION STARTED: Hunting leads in {0}, {1}".format(city, state))
        try:
            service = build("customsearch", "v1", developerKey=api_key)
            keywords = ["must sell", "cash deal", "motivated seller", "probate deal"]
            total = 0
            for kw in keywords:
                for start in range(1, 101, 10):
                    q = '"{0}" "{1}" {2}'.format(city, state, kw)
                    res = service.cse().list(q=q, cx=cx, num=10, start=start).execute()
                    if 'items' not in res: break
                    for item in res.get('items', []):
                        snippet = (item.get('snippet', '') + " " + item.get('title', '')).lower()
                        link = item.get('link', '#')
                        phones = re.findall(r'\(?\d{}\)?[-.\s]?\d{}[-.\s]?\d{}', snippet)
                        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', snippet)
                        if phones or emails:
                            if not Lead.query.filter_by(link=link, submitter_id=user_id).first():
                                o_name = "Property Owner"
                                l = Lead(submitter_id=user_id, address=item.get('title')[:100], name=o_name, phone=phones[0] if phones else "None", email=emails[0] if emails else "None", link=link)
                                db.session.add(l); total += 1; log_activity("✅ HARVESTED: {0}".format(l.address[:25]))
                    db.session.commit()
                    time.sleep(random.uniform(5, 15)) 
            log_activity("🏁 MISSION COMPLETE: indexed {0} leads.".format(total))
        except Exception as e: log_activity("⚠️ SCRAPE FAULT: {0}".format(str(e)))

def industrial_outreach(app, user_id, subject, body, groq):
    """ Mass Outreach engine with dynamicinjection. """
    with app.app_context():
        user = User.query.get(user_id)
        leads = Lead.query.filter(Lead.submitter_id == user_id, Lead.email.contains('@')).all()
        log_activity("📧 BLAST STARTED: {0} leads.".format(len(leads)))
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls(); server.login(user.smtp_email, user.smtp_password)
            for lead in leads:
                try:
                    final = body if body and len(body) > 10 else user.email_template
                    final = final.replace("[[ADDRESS]]", lead.address).replace("[[NAME]]", lead.name)
                    msg = MIMEMultipart(); msg['From'] = user.smtp_email; msg['To'] = lead.email; msg['Subject'] = subject.replace("[[ADDRESS]]", lead.address)
                    msg.attach(MIMEText(final, 'plain')); server.send_message(msg)
                    out = OutreachLog(user_id=user_id, recipient_email=lead.email, address=lead.address, message=final[:250])
                    db.session.add(out); lead.emailed_count += 1; lead.status = "Contacted"; db.session.commit()
                    log_activity("📨 SENT SUCCESS: {0}".format(lead.email)); time.sleep(random.uniform(5, 15))
                except Exception as e: log_activity("⚠️ SMTP FAIL ({0}): {1}".format(lead.email, str(e)))
            server.quit()
        except Exception as e: log_activity("❌ SMTP CRITICAL: {0}".format(str(e)))
