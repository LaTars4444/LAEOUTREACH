import random
import time
import json
from datetime import datetime, timedelta

# COMPREHENSIVE 50-STATE INDUSTRIAL CITY DATABASE
USA_STATES = {
    "AL": ["Birmingham", "Montgomery", "Mobile", "Huntsville", "Tuscaloosa"],
    "AK": ["Anchorage", "Juneau", "Fairbanks", "Sitka", "Ketchikan"],
    "AZ": ["Phoenix", "Tucson", "Mesa", "Scottsdale", "Chandler", "Glendale"],
    "AR": ["Little Rock", "Fort Smith", "Fayetteville", "Springdale", "Jonesboro"],
    "CA": ["Los Angeles", "San Diego", "San Francisco", "Sacramento", "Fresno", "San Jose"],
    "CO": ["Denver", "Colorado Springs", "Aurora", "Fort Collins", "Lakewood"],
    "CT": ["Hartford", "Bridgeport", "Stamford", "New Haven", "Waterbury"],
    "DE": ["Wilmington", "Dover", "Newark", "Middletown", "Smyrna"],
    "FL": ["Miami", "Tampa", "Orlando", "Jacksonville", "Fort Lauderdale", "Tallahassee"],
    "GA": ["Atlanta", "Savannah", "Augusta", "Columbus", "Macon", "Athens"],
    "HI": ["Honolulu", "Hilo", "Kailua", "Kapolei", "Lahaina"],
    "ID": ["Boise", "Meridian", "Nampa", "Idaho Falls", "Pocatello"],
    "IL": ["Chicago", "Aurora", "Rockford", "Springfield", "Joliet"],
    "IN": ["Indianapolis", "Fort Wayne", "Evansville", "South Bend", "Carmel"],
    "IA": ["Des Moines", "Cedar Rapids", "Davenport", "Sioux City", "Iowa City"],
    "KS": ["Wichita", "Overland Park", "Kansas City", "Topeka", "Olathe"],
    "KY": ["Louisville", "Lexington", "Bowling Green", "Owensboro", "Covington"],
    "LA": ["New Orleans", "Baton Rouge", "Shreveport", "Lafayette", "Lake Charles"],
    "ME": ["Portland", "Lewiston", "Bangor", "South Portland", "Auburn"],
    "MD": ["Baltimore", "Frederick", "Rockville", "Gaithersburg", "Bowie"],
    "MA": ["Boston", "Worcester", "Springfield", "Cambridge", "Lowell"],
    "MI": ["Detroit", "Grand Rapids", "Warren", "Sterling Heights", "Ann Arbor"],
    "MN": ["Minneapolis", "St. Paul", "Rochester", "Duluth", "Bloomington"],
    "MS": ["Jackson", "Gulfport", "Southaven", "Biloxi", "Hattiesburg"],
    "MO": ["Kansas City", "St. Louis", "Springfield", "Columbia", "Independence"],
    "MT": ["Billings", "Missoula", "Great Falls", "Bozeman", "Butte"],
    "NE": ["Omaha", "Lincoln", "Bellevue", "Grand Island", "Kearney"],
    "NV": ["Las Vegas", "Henderson", "Reno", "North Las Vegas", "Sparks"],
    "NH": ["Manchester", "Nashua", "Concord", "Derry", "Dover"],
    "NJ": ["Newark", "Jersey City", "Paterson", "Elizabeth", "Edison"],
    "NM": ["Albuquerque", "Las Cruces", "Rio Rancho", "Santa Fe", "Roswell"],
    "NY": ["New York City", "Buffalo", "Rochester", "Yonkers", "Albany", "Syracuse"],
    "NC": ["Charlotte", "Raleigh", "Greensboro", "Durham", "Winston-Salem"],
    "ND": ["Fargo", "Bismarck", "Grand Forks", "Minot", "West Fargo"],
    "OH": ["Columbus", "Cleveland", "Cincinnati", "Toledo", "Akron", "Dayton"],
    "OK": ["Oklahoma City", "Tulsa", "Norman", "Broken Arrow", "Edmond"],
    "OR": ["Portland", "Salem", "Eugene", "Gresham", "Hillsboro"],
    "PA": ["Philadelphia", "Pittsburgh", "Allentown", "Erie", "Reading", "Scranton"],
    "RI": ["Providence", "Warwick", "Cranston", "Pawtucket", "East Providence"],
    "SC": ["Charleston", "Columbia", "North Charleston", "Mount Pleasant", "Rock Hill"],
    "SD": ["Sioux Falls", "Rapid City", "Aberdeen", "Brookings", "Watertown"],
    "TN": ["Nashville", "Memphis", "Knoxville", "Chattanooga", "Clarksville"],
    "TX": ["Houston", "Dallas", "Austin", "San Antonio", "Fort Worth", "El Paso"],
    "UT": ["Salt Lake City", "West Valley City", "Provo", "West Jordan", "Orem"],
    "VT": ["Burlington", "South Burlington", "Rutland", "Barre", "Montpelier"],
    "VA": ["Virginia Beach", "Norfolk", "Chesapeake", "Richmond", "Newport News"],
    "WA": ["Seattle", "Spokane", "Tacoma", "Vancouver", "Bellevue", "Kent"],
    "WV": ["Charleston", "Huntington", "Morgantown", "Parkersburg", "Wheeling"],
    "WI": ["Milwaukee", "Madison", "Green Bay", "Kenosha", "Racine"],
    "WY": ["Cheyenne", "Casper", "Laramie", "Gillette", "Rock Springs"]
}

def stealth_behavior():
    """ Mandatory industrial delay to prevent network ban. """
    time.sleep(random.uniform(5, 15))

def check_access(user, feature):
    """ Industrial trial and subscription validation. """
    if not user: return False
    if user.subscription_status in ['lifetime', 'monthly', 'weekly']:
        if user.subscription_status == 'lifetime' or (user.subscription_end and user.subscription_end > datetime.utcnow()):
            return True
    now = datetime.utcnow()
    trial_start = user.created_at
    if feature == 'email' and now < trial_start + timedelta(hours=24): return True
    if feature == 'ai' and now < trial_start + timedelta(hours=48): return True
    return False
Module 4: tasks.py
Industrial Scraper and Outreach machine.

"""
TITAN INDUSTRIAL ENGINES - V11.0.0
==================================
Industrial Lead Hunter (optimized for 1,000 site network).
Outreach Machine (dynamic universal templates).
"""
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
from utils import stealth_behavior

# Global production buffer
SYSTEM_LOGS = []

def log_activity(message):
    """ Surgical Indexed Formatting Engine. """
    try:
        timestamp = time.strftime("%H:%M:%S")
        log_format = "[{0}] {1}"
        entry = log_format.format(timestamp, message)
        print(entry)
        SYSTEM_LOGS.insert(0, entry)
        if len(SYSTEM_LOGS) > 5000: SYSTEM_LOGS.pop()
    except: pass

def vicious_hunter(app, user_id, city, state, api_key, cx):
    """ Optimized for 1,000 site networks. Deep Pagination loop. """
    with app.app_context():
        log_activity("🚀 MISSION STARTED: Hunting in {0}, {1}".format(city, state))
        try:
            service = build("customsearch", "v1", developerKey=api_key)
            keywords = ["must sell", "cash buyer", "motivated seller", "probate deal", "divorce sale"]
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
                                # Owner extraction heuristic
                                o_name = "Property Owner"
                                nm = re.search(r'by\s+([a-zA-Z]+)', snippet)
                                if nm: o_name = nm.group(1).capitalize()
                                l = Lead(submitter_id=user_id, address=item.get('title')[:100], name=o_name, phone=phones[0] if phones else "None", email=emails[0] if emails else "None", link=link)
                                db.session.add(l); total += 1; log_activity("✅ HARVESTED: {0}".format(l.address[:25]))
                    db.session.commit(); stealth_behavior()
            log_activity("🏁 MISSION COMPLETE: {0} leads indexed.".format(total))
        except Exception as e: log_activity("⚠️ SCRAPE FAULT: {0}".format(str(e)))

def outreach_machine(app, user_id, subject, body, groq):
    """ Dynamic injection Outreach Machine. """
    with app.app_context():
        user = User.query.get(user_id)
        leads = Lead.query.filter(Lead.submitter_id == user_id, Lead.email.contains('@')).all()
        log_activity("📧 BLAST STARTING: {0} leads.".format(len(leads)))
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls(); server.login(user.smtp_email, user.smtp_password)
            for lead in leads:
                try:
                    final_body = body if body and len(body) > 10 else user.email_template
                    final_body = final_body.replace("[[ADDRESS]]", lead.address).replace("[[NAME]]", lead.name)
                    msg = MIMEMultipart(); msg['From'] = user.smtp_email; msg['To'] = lead.email; msg['Subject'] = subject.replace("[[ADDRESS]]", lead.address)
                    msg.attach(MIMEText(final_body, 'plain')); server.send_message(msg)
                    # Sentence history log
                    out = OutreachLog(user_id=user_id, recipient_email=lead.email, address=lead.address, message=final_body[:200])
                    db.session.add(out); lead.emailed_count += 1; lead.status = "Contacted"; db.session.commit()
                    log_activity("📨 SENT: {0}".format(lead.email)); stealth_behavior()
                except Exception as e: log_activity("⚠️ SMTP FAIL ({0}): {1}".format(lead.email, str(e)))
            server.quit(); log_activity("🏁 BLAST COMPLETE.")
        except Exception as e: log_activity("❌ SMTP CRITICAL: {0}".format(str(e)))
