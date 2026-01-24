import random
import time
import json
from datetime import datetime, timedelta

# COMPREHENSIVE 50-STATE INDUSTRIAL CITY CLUSTER DATABASE
# Includes major hubs for high-volume lead extraction.
USA_STATES = {
    "AL": ["Birmingham", "Montgomery", "Mobile", "Huntsville", "Tuscaloosa", "Dothan", "Auburn"],
    "AK": ["Anchorage", "Juneau", "Fairbanks", "Sitka", "Ketchikan", "Wasilla"],
    "AZ": ["Phoenix", "Tucson", "Mesa", "Scottsdale", "Chandler", "Glendale", "Gilbert"],
    "AR": ["Little Rock", "Fort Smith", "Fayetteville", "Springdale", "Jonesboro", "Rogers"],
    "CA": ["Los Angeles", "San Diego", "San Francisco", "Sacramento", "Fresno", "San Jose", "Oakland"],
    "CO": ["Denver", "Colorado Springs", "Aurora", "Fort Collins", "Lakewood", "Thornton"],
    "CT": ["Hartford", "Bridgeport", "Stamford", "New Haven", "Waterbury", "Danbury"],
    "DE": ["Wilmington", "Dover", "Newark", "Middletown", "Smyrna", "Milford"],
    "FL": ["Miami", "Tampa", "Orlando", "Jacksonville", "Fort Lauderdale", "Tallahassee", "Naples"],
    "GA": ["Atlanta", "Savannah", "Augusta", "Columbus", "Macon", "Athens", "Sandy Springs"],
    "HI": ["Honolulu", "Hilo", "Kailua", "Kapolei", "Lahaina"],
    "ID": ["Boise", "Meridian", "Nampa", "Idaho Falls", "Pocatello", "Caldwell"],
    "IL": ["Chicago", "Aurora", "Rockford", "Springfield", "Joliet", "Naperville", "Peoria"],
    "IN": ["Indianapolis", "Fort Wayne", "Evansville", "South Bend", "Carmel", "Fishers"],
    "IA": ["Des Moines", "Cedar Rapids", "Davenport", "Sioux City", "Iowa City", "Waterloo"],
    "KS": ["Wichita", "Overland Park", "Kansas City", "Topeka", "Olathe", "Lawrence"],
    "KY": ["Louisville", "Lexington", "Bowling Green", "Owensboro", "Covington"],
    "LA": ["New Orleans", "Baton Rouge", "Shreveport", "Lafayette", "Lake Charles", "Kenner"],
    "ME": ["Portland", "Lewiston", "Bangor", "South Portland", "Auburn", "Biddeford"],
    "MD": ["Baltimore", "Frederick", "Rockville", "Gaithersburg", "Bowie", "Hagerstown"],
    "MA": ["Boston", "Worcester", "Springfield", "Cambridge", "Lowell", "Brockton"],
    "MI": ["Detroit", "Grand Rapids", "Warren", "Sterling Heights", "Ann Arbor", "Lansing"],
    "MN": ["Minneapolis", "St. Paul", "Rochester", "Duluth", "Bloomington", "Brooklyn Park"],
    "MS": ["Jackson", "Gulfport", "Southaven", "Biloxi", "Hattiesburg", "Olive Branch"],
    "MO": ["Kansas City", "St. Louis", "Springfield", "Columbia", "Independence", "Lee's Summit"],
    "MT": ["Billings", "Missoula", "Great Falls", "Bozeman", "Butte", "Helena"],
    "NE": ["Omaha", "Lincoln", "Bellevue", "Grand Island", "Kearney", "Fremont"],
    "NV": ["Las Vegas", "Henderson", "Reno", "North Las Vegas", "Sparks", "Carson City"],
    "NH": ["Manchester", "Nashua", "Concord", "Derry", "Dover", "Rochester"],
    "NJ": ["Newark", "Jersey City", "Paterson", "Elizabeth", "Edison", "Woodbridge"],
    "NM": ["Albuquerque", "Las Cruces", "Rio Rancho", "Santa Fe", "Roswell", "Farmington"],
    "NY": ["New York City", "Buffalo", "Rochester", "Yonkers", "Albany", "Syracuse"],
    "NC": ["Charlotte", "Raleigh", "Greensboro", "Durham", "Winston-Salem", "Fayetteville"],
    "ND": ["Fargo", "Bismarck", "Grand Forks", "Minot", "West Fargo", "Williston"],
    "OH": ["Columbus", "Cleveland", "Cincinnati", "Toledo", "Akron", "Dayton", "Parma"],
    "OK": ["Oklahoma City", "Tulsa", "Norman", "Broken Arrow", "Edmond", "Lawton"],
    "OR": ["Portland", "Salem", "Eugene", "Gresham", "Hillsboro", "Beaverton"],
    "PA": ["Philadelphia", "Pittsburgh", "Allentown", "Erie", "Reading", "Scranton"],
    "RI": ["Providence", "Warwick", "Cranston", "Pawtucket", "East Providence"],
    "SC": ["Charleston", "Columbia", "North Charleston", "Mount Pleasant", "Rock Hill"],
    "SD": ["Sioux Falls", "Rapid City", "Aberdeen", "Brookings", "Watertown"],
    "TN": ["Nashville", "Memphis", "Knoxville", "Chattanooga", "Clarksville", "Murfreesboro"],
    "TX": ["Houston", "Dallas", "Austin", "San Antonio", "Fort Worth", "El Paso", "Arlington"],
    "UT": ["Salt Lake City", "West Valley City", "Provo", "West Jordan", "Orem"],
    "VT": ["Burlington", "South Burlington", "Rutland", "Barre", "Montpelier"],
    "VA": ["Virginia Beach", "Norfolk", "Chesapeake", "Richmond", "Newport News"],
    "WA": ["Seattle", "Spokane", "Tacoma", "Vancouver", "Bellevue", "Kent", "Everett"],
    "WV": ["Charleston", "Huntington", "Morgantown", "Parkersburg", "Wheeling"],
    "WI": ["Milwaukee", "Madison", "Green Bay", "Kenosha", "Racine", "Appleton"],
    "WY": ["Cheyenne", "Casper", "Laramie", "Gillette", "Rock Springs", "Sheridan"]
}

def human_stealth_delay():
    """ Industrial Stealth Protocol: randomized 5-15s behavioral jitter. """
    time.sleep(random.uniform(5, 15))

def check_access(user, feature):
    """
    Industrial Access Control Logic.
    Validates features against Trial, Subscription, and Lifetime tiers.
    """
    if not user: return False
    # Paid tier validation
    if user.subscription_status in ['lifetime', 'monthly', 'weekly']:
        if user.subscription_status == 'lifetime' or (user.subscription_end and user.subscription_end > datetime.utcnow()):
            return True
    # Time-based trial validation logic
    now = datetime.utcnow()
    trial_start = user.created_at
    if feature == 'email' and now < trial_start + timedelta(hours=24): return True
    if feature == 'ai' and now < trial_start + timedelta(hours=48): return True
    return False
