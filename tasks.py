
import os
import random
import re
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from googleapiclient.discovery import build
from extensions import db
from models import Lead, OutreachLog, User
from utils import industrial_decrypt, human_stealth_delay

# ----------------------------------------------------------------------------------------------------------------------
# 0. INDUSTRIAL LOGGING ENGINE
# ----------------------------------------------------------------------------------------------------------------------
# Standardized log buffer for the real-time terminal.
# SURGICAL FIX: Uses Explicit Manual Indexing {0} to prevent Render SyntaxErrors.
# ----------------------------------------------------------------------------------------------------------------------
SYSTEM_LOGS = []

def log_activity(message):
    """
    Pushes status telemetry to the memory buffer and server console.
    Guaranteed stability on Render by avoiding automatic field numbering.
    """
    try:
        timestamp = time.strftime("%H:%M:%S")
        
        # INDUSTRIAL INDEXED FORMATTING
        log_format = "[{0}] {1}"
        entry = log_format.format(timestamp, message)
        
        print(entry)
        SYSTEM_LOGS.insert(0, entry)
        
        # Buffer cap for high-volume enterprise production
        if len(SYSTEM_LOGS) > 5000: 
            SYSTEM_LOGS.pop()
    except Exception as e:
        print("CRITICAL LOGGER ERROR: {0}".format(str(e)))

# ----------------------------------------------------------------------------------------------------------------------
# 1. VICIOUS HUNTER SCRAPER (1,000 SITE OPTIMIZED)
# ----------------------------------------------------------------------------------------------------------------------

def task_vicious_hunter(app, user_id, city, state, api_key, cx):
    """
    INDUSTRIAL LEAD HARVESTER.
    Optimized for searching across a massive 1,000-site Google CX Network.
    
    STANDARDS:
    - Combinatorial query generation.
    - Deep 10-page pagination loop (100 results per keyword).
    - Mandatory human behavior emulation (5-15s delay).
    - Data deduplication via link verification.
    """
    with app.app_context():
        start_log = "🚀 MISSION STARTED: Lead Extraction in {0}, {1}".format(city, state)
        log_activity(start_log)
        
        try:
            # Initialize Google Enterprise Service
            service = build("customsearch", "v1", developerKey=api_key)
            
            # High-intent real estate keywords for combinatorial search
            keywords = [
                "must sell", "motivated seller", "cash only", "probate deal", 
                "divorce sale", "fixer upper", "inherited house", "tired landlord",
                "back on market", "Creative financing", "foreclosure notice"
            ]
            
            total_added = 0
            
            for kw in keywords:
                # DEEP PAGINATION LOOP: Iterates through start indices (1, 11, 21... 91)
                for start_idx in range(1, 101, 10):
                    
                    # ENTERPRISE NETWORK QUERY logic
                    query_format = '"{0}" "{1}" {2}'
                    q = query_format.format(city, state, kw)
                    
                    # Execute API Call
                    response = service.cse().list(q=q, cx=cx, num=10, start=start_idx).execute()
                    
                    if 'items' not in response:
                        break # Terminate keyword if results exhausted

                    for item in response.get('items', []):
                        snippet = (item.get('snippet', '') + " " + item.get('title', '')).lower()
                        link = item.get('link', '#')
                        
                        # INDUSTRIAL REGEX PIPELINE: Phone & Email extraction
                        phones = re.findall(r'\(?\d{}\)?[-.\s]?\d{}[-.\s]?\d{}', snippet)
                        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', snippet)
                        
                        if phones or emails:
                            # DEDUPLICATION GATEWAY
                            if not Lead.query.filter_by(link=link, submitter_id=user_id).first():
                                
                                # Property Owner Name heuristic extraction
                                o_name = "Property Owner"
                                name_find = re.search(r'by\s+([a-zA-Z]+)', snippet)
                                if name_find: 
                                    o_name = name_find.group(1).capitalize()

                                # Create Lead Record
                                l = Lead(
                                    submitter_id=user_id,
                                    address=item.get('title')[:100],
                                    name=o_name,
                                    phone=phones[0] if phones else "None",
                                    email=emails[0] if emails else "None",
                                    source="Industrial Cluster",
                                    link=link,
                                    status="New"
                                )
                                db.session.add(l)
                                total_added += 1
                                
                                harvest_log = "✅ HARVESTED: {0}".format(l.address[:25])
                                log_activity(harvest_log)
                    
                    # Commit and Pause to mimic human research patterns
                    db.session.commit()
                    human_stealth_delay() 
            
            log_activity("🏁 MISSION COMPLETE: indexed {0} leads.".format(total_added))
            
        except Exception as e:
            log_activity("⚠️ SCRAPE FAULT: {0}".format(str(e)))

# ----------------------------------------------------------------------------------------------------------------------
# 2. OUTREACH MACHINE (UNIVERSAL SCRIPT ENGINE)
# ----------------------------------------------------------------------------------------------------------------------

def task_outreach_machine(app, user_id, subject, body, groq_client, master_key):
    """
    INDUSTRIAL OUTREACH ENGINE.
    Functional standards:
    - Secure App Password decryption.
    - Universal Script support with dynamic injection ([[ADDRESS]], [[NAME]]).
    - AI-Personalization override via Groq Llama 3.3.
    - Mandatory stealth jitter (5-15s randomized sleep).
    """
    with app.app_context():
        user = User.query.get(user_id)
        
        # INDUSTRIAL DECRYPTION OF GMAIL KEYS
        try:
            decrypted_app_pass = industrial_decrypt(user.smtp_password_encrypted, master_key)
        except:
            log_activity("❌ DECRYPTION ERROR: Master key mismatch.")
            return

        if not user.smtp_email or not decrypted_app_pass:
            log_activity("❌ SMTP ERROR: Gmail configuration incomplete.")
            return

        # Target leads with valid email addresses
        leads = Lead.query.filter(Lead.submitter_id == user_id, Lead.email.contains('@')).all()
        log_activity("📧 BLAST STARTING: Targeting {0} leads.".format(len(leads)))
        
        try:
            # Initialize SMTP Production Session
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(user.smtp_email, decrypted_app_pass)
            log_activity("✅ SMTP LOGIN: SUCCESS.")
            
            count = 0
            for lead in leads:
                try:
                    # DYNAMIC DATA INJECTION ENGINE
                    # Swaps tags [[ADDRESS]] and [[NAME]] with real-time database data
                    final_msg = body if body and len(body) > 10 else user.email_template
                    final_msg = final_msg.replace("[[ADDRESS]]", lead.address)
                    final_msg = final_msg.replace("[[NAME]]", lead.name or "Property Owner")
                    
                    # AI SMART ENHANCEMENT (GROQ LLAMA 3.3)
                    # If final message is short, AI expands it into a unique professional offer
                    if groq_client and len(final_msg) < 20:
                        chat = groq_client.chat.completions.create(
                            messages=[{"role": "user", "content": "Write a short cash offer for {0} at {1}.".format(lead.name, lead.address)}],
                            model="llama-3.3-70b-versatile"
                        )
                        final_msg = chat.choices[0].message.content

                    # Construct MIME Envelope
                    msg = MIMEMultipart()
                    msg['From'] = user.smtp_email
                    msg['To'] = lead.email
                    msg['Subject'] = subject.replace("[[ADDRESS]]", lead.address)
                    msg.attach(MIMEText(final_msg, 'plain'))
                    
                    # Execute Transmission
                    server.send_message(msg)
                    
                    # PERSISTENT HISTORY LOGGING (Visibility Pane Support)
                    out = OutreachLog(
                        user_id=user_id, 
                        recipient_email=lead.email, 
                        address=lead.address, 
                        message=final_msg[:250],
                        status="Delivered"
                    )
                    db.session.add(out)
                    
                    # Update Lead Metadata
                    lead.emailed_count = (lead.emailed_count or 0) + 1
                    lead.status = "Contacted"
                    db.session.commit()
                    
                    count += 1
                    log_activity("📨 SENT SUCCESS: {0}".format(lead.email))
                    
                    # Mandatory Stealth Delay to prevent Gmail IP ban
                    human_stealth_delay()
                    
                except Exception as e:
                    log_activity("⚠️ SMTP FAIL ({0}): {1}".format(lead.email, str(e)))
            
            server.quit()
            log_activity("🏁 BLAST COMPLETE: {0} deliveries confirmed.".format(count))
            
        except Exception as e:
            log_activity("❌ SMTP CRITICAL ERROR: {0}".format(str(e)))
