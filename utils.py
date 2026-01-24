import json
from datetime import datetime, timedelta

# COMPREHENSIVE 50-STATE INDUSTRIAL DATABASE
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
    "IA": ["Des Moines", "Cedar Rapids", "Davenport"],
    "KS": ["Wichita", "Overland Park", "Kansas City"],
    "KY": ["Louisville", "Lexington", "Bowling Green"],
    "LA": ["New Orleans", "Baton Rouge", "Shreveport"],
    "ME": ["Portland", "Lewiston", "Bangor"],
    "MD": ["Baltimore", "Frederick", "Rockville"],
    "MA": ["Boston", "Worcester", "Springfield", "Cambridge"],
    "MI": ["Detroit", "Grand Rapids", "Warren", "Sterling Heights"],
    "MN": ["Minneapolis", "St. Paul", "Rochester", "Duluth"],
    "MS": ["Jackson", "Gulfport", "Southaven"],
    "MO": ["Kansas City", "St. Louis", "Springfield", "Columbia"],
    "MT": ["Billings", "Missoula", "Great Falls"],
    "NE": ["Omaha", "Lincoln", "Bellevue"],
    "NV": ["Las Vegas", "Henderson", "Reno", "North Las Vegas"],
    "NH": ["Manchester", "Nashua", "Concord"],
    "NJ": ["Newark", "Jersey City", "Paterson", "Elizabeth"],
    "NM": ["Albuquerque", "Las Cruces", "Rio Rancho", "Santa Fe"],
    "NY": ["New York City", "Buffalo", "Rochester", "Yonkers", "Albany"],
    "NC": ["Charlotte", "Raleigh", "Greensboro", "Durham", "Winston-Salem"],
    "ND": ["Fargo", "Bismarck", "Grand Forks"],
    "OH": ["Columbus", "Cleveland", "Cincinnati", "Toledo", "Akron"],
    "OK": ["Oklahoma City", "Tulsa", "Norman", "Broken Arrow"],
    "OR": ["Portland", "Salem", "Eugene", "Gresham"],
    "PA": ["Philadelphia", "Pittsburgh", "Allentown", "Erie", "Reading"],
    "RI": ["Providence", "Warwick", "Cranston"],
    "SC": ["Charleston", "Columbia", "North Charleston", "Mount Pleasant"],
    "SD": ["Sioux Falls", "Rapid City"],
    "TN": ["Nashville", "Memphis", "Knoxville", "Chattanooga"],
    "TX": ["Houston", "Dallas", "Austin", "San Antonio", "Fort Worth"],
    "UT": ["Salt Lake City", "West Valley City", "Provo", "West Jordan"],
    "VT": ["Burlington", "South Burlington"],
    "VA": ["Virginia Beach", "Norfolk", "Chesapeake", "Richmond"],
    "WA": ["Seattle", "Spokane", "Tacoma", "Vancouver", "Bellevue"],
    "WV": ["Charleston", "Huntington", "Morgantown"],
    "WI": ["Milwaukee", "Madison", "Green Bay", "Kenosha"],
    "WY": ["Cheyenne", "Casper", "Laramie"]
}

def check_access(user, feature):
    """ Industrial standard access control engine. """
    if not user: return False
    if user.subscription_status in ['lifetime', 'monthly', 'weekly']:
        if user.subscription_status == 'lifetime' or (user.subscription_end and user.subscription_end > datetime.utcnow()):
            return True
    
    now = datetime.utcnow()
    trial_start = user.created_at
    if feature == 'email' and now < trial_start + timedelta(hours=24): return True
    if feature == 'ai' and now < trial_start + timedelta(hours=48): return True
    return False
