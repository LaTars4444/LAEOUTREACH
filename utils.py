import random
import time
from datetime import datetime, timedelta

# COMPREHENSIVE 50-STATE INDUSTRIAL CITY DATABASE
USA_STATES = {
    "AL": ["Birmingham", "Montgomery", "Mobile", "Huntsville", "Tuscaloosa"],
    "AK": ["Anchorage", "Juneau", "Fairbanks"],
    "AZ": ["Phoenix", "Tucson", "Mesa", "Scottsdale", "Chandler"],
    "AR": ["Little Rock", "Fort Smith", "Fayetteville"],
    "CA": ["Los Angeles", "San Diego", "San Francisco", "Sacramento", "Fresno"],
    "CO": ["Denver", "Colorado Springs", "Aurora", "Fort Collins"],
    "CT": ["Hartford", "Bridgeport", "Stamford", "New Haven"],
    "DE": ["Wilmington", "Dover", "Newark"],
    "FL": ["Miami", "Tampa", "Orlando", "Jacksonville", "Fort Lauderdale"],
    "GA": ["Atlanta", "Savannah", "Augusta", "Columbus"],
    "HI": ["Honolulu", "Hilo", "Kailua"],
    "ID": ["Boise", "Meridian", "Nampa"],
    "IL": ["Chicago", "Aurora", "Rockford", "Springfield"],
    "IN": ["Indianapolis", "Fort Wayne", "Evansville"],
    "IA": ["Des Moines", "Cedar Rapids", "Daven Iowa"],
    "KS": ["Wichita", "Topeka", "Olathe"],
    "KY": ["Louisville", "Lexington", "Bowling Green"],
    "LA": ["New Orleans", "Baton Rouge", "Shreveport"],
    "ME": ["Portland", "Lewiston", "Bangor"],
    "MD": ["Baltimore", "Frederick", "Rockville"],
    "MA": ["Boston", "Worcester", "Springfield"],
    "MI": ["Detroit", "Grand Rapids", "Warren"],
    "MN": ["Minneapolis", "St. Paul", "Rochester"],
    "MS": ["Jackson", "Gulfport", "Southaven"],
    "MO": ["Kansas City", "St. Louis", "Springfield"],
    "MT": ["Billings", "Missoula", "Great Falls"],
    "NE": ["Omaha", "Lincoln", "Bellevue"],
    "NV": ["Las Vegas", "Henderson", "Reno"],
    "NH": ["Manchester", "Nashua", "Concord"],
    "NJ": ["Newark", "Jersey City", "Paterson"],
    "NM": ["Albuquerque", "Las Cruces", "Santa Fe"],
    "NY": ["New York City", "Buffalo", "Rochester"],
    "NC": ["Charlotte", "Raleigh", "Greensboro"],
    "ND": ["Fargo", "Bismarck", "Grand Forks"],
    "OH": ["Columbus", "Cleveland", "Cincinnati"],
    "OK": ["Oklahoma City", "Tulsa", "Norman"],
    "OR": ["Portland", "Salem", "Eugene"],
    "PA": ["Philadelphia", "Pittsburgh", "Allentown"],
    "RI": ["Providence", "Warwick", "Cranston"],
    "SC": ["Charleston", "Columbia", "North Charleston"],
    "SD": ["Sioux Falls", "Rapid City", "Aberdeen"],
    "TN": ["Nashville", "Memphis", "Knoxville"],
    "TX": ["Houston", "Dallas", "Austin", "San Antonio"],
    "UT": ["Salt Lake City", "West Valley City", "Provo"],
    "VT": ["Burlington", "South Burlington"],
    "VA": ["Virginia Beach", "Norfolk", "Chesapeake"],
    "WA": ["Seattle", "Spokane", "Tacoma"],
    "WV": ["Charleston", "Huntington", "Morgantown"],
    "WI": ["Milwaukee", "Madison", "Green Bay"],
    "WY": ["Cheyenne", "Casper", "Laramie"]
}

def human_stealth_delay():
    """Industrial Stealth Protocol: randomized 5-15s behavioral delay."""
    time.sleep(random.uniform(5, 15))

def check_access(user, feature):
    """ Industrial trial and subscription access gateway. """
    if not user: return False
    if user.subscription_status in ['lifetime', 'monthly', 'weekly']:
        if user.subscription_status == 'lifetime' or (user.subscription_end and user.subscription_end > datetime.utcnow()):
            return True
    now = datetime.utcnow()
    trial_start = user.created_at
    if feature == 'email' and now < trial_start + timedelta(hours=24): return True
    if feature == 'ai' and now < trial_start + timedelta(hours=48): return True
    return False
