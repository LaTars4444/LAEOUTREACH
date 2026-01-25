import random
import time
from datetime import datetime, timedelta

# EXHAUSTIVE 50-STATE INDUSTRIAL CITY CLUSTER DATABASE
# Optimized for industrial-scale lead harvesting.
USA_STATES = {
    "AL": ["Birmingham", "Montgomery", "Mobile", "Huntsville", "Tuscaloosa", "Dothan", "Auburn", "Decatur", "Madison", "Florence"],
    "AK": ["Anchorage", "Juneau", "Fairbanks", "Sitka", "Ketchikan", "Wasilla", "Kenai", "Kodiak", "Bethel", "Palmer"],
    "AZ": ["Phoenix", "Tucson", "Mesa", "Scottsdale", "Chandler", "Glendale", "Gilbert", "Yuma", "Peoria", "Tempe"],
    "AR": ["Little Rock", "Fort Smith", "Fayetteville", "Springdale", "Jonesboro", "Rogers", "Conway", "Bentonville", "Pine Bluff"],
    "CA": ["Los Angeles", "San Diego", "San Francisco", "Sacramento", "Fresno", "San Jose", "Oakland", "Anaheim", "Bakersfield", "Riverside"],
    "CO": ["Denver", "Colorado Springs", "Aurora", "Fort Collins", "Lakewood", "Thornton", "Arvada", "Westminster", "Pueblo", "Greeley"],
    "CT": ["Hartford", "Bridgeport", "Stamford", "New Haven", "Waterbury", "Danbury", "Norwalk", "New Britain", "West Hartford"],
    "DE": ["Wilmington", "Dover", "Newark", "Middletown", "Smyrna", "Milford", "Seaford", "Georgetown", "Elsmere", "New Castle"],
    "FL": ["Miami", "Tampa", "Orlando", "Jacksonville", "Fort Lauderdale", "Tallahassee", "Naples", "Ocala", "Gainesville", "Pensacola"],
    "GA": ["Atlanta", "Savannah", "Augusta", "Columbus", "Macon", "Athens", "Sandy Springs", "Roswell", "Johns Creek", "Warner Robins"],
    "HI": ["Honolulu", "Hilo", "Kailua", "Kapolei", "Lahaina", "Waipahu", "Pearl City", "Kaneole", "Mililani", "Ewa Beach"],
    "ID": ["Boise", "Meridian", "Nampa", "Idaho Falls", "Pocatello", "Caldwell", "Coeur d'Alene", "Twin Falls", "Post Falls", "Lewiston"],
    "IL": ["Chicago", "Aurora", "Rockford", "Springfield", "Joliet", "Naperville", "Peoria", "Elgin", "Waukegan", "Champaign"],
    "IN": ["Indianapolis", "Fort Wayne", "Evansville", "South Bend", "Carmel", "Fishers", "Bloomington", "Hammond", "Gary", "Lafayette"],
    "IA": ["Des Moines", "Cedar Rapids", "Davenport", "Sioux City", "Iowa City", "Waterloo", "Ames", "West Des Moines", "Council Bluffs"],
    "KS": ["Wichita", "Overland Park", "Kansas City", "Topeka", "Olathe", "Lawrence", "Shawnee", "Manhattan", "Lenexa", "Salina"],
    "KY": ["Louisville", "Lexington", "Bowling Green", "Owensboro", "Covington", "Hopkinsville", "Richmond", "Florence", "Georgetown"],
    "LA": ["New Orleans", "Baton Rouge", "Shreveport", "Lafayette", "Lake Charles", "Kenner", "Bossier City", "Monroe", "Alexandria"],
    "ME": ["Portland", "Lewiston", "Bangor", "South Portland", "Auburn", "Biddeford", "Augusta", "Saco", "Westbrook", "Waterville"],
    "MD": ["Baltimore", "Frederick", "Rockville", "Gaithersburg", "Bowie", "Hagerstown", "Annapolis", "Salisbury", "College Park"],
    "MA": ["Boston", "Worcester", "Springfield", "Cambridge", "Lowell", "Brockton", "Quincy", "Lynn", "New Bedford", "Fall River"],
    "MI": ["Detroit", "Grand Rapids", "Warren", "Sterling Heights", "Ann Arbor", "Lansing", "Flint", "Dearborn", "Livonia", "Troy"],
    "MN": ["Minneapolis", "St. Paul", "Rochester", "Duluth", "Bloomington", "Brooklyn Park", "Plymouth", "Woodbury", "Eagan", "Blaine"],
    "MS": ["Jackson", "Gulfport", "Southaven", "Biloxi", "Hattiesburg", "Olive Branch", "Tupelo", "Meridian", "Clinton", "Pearl"],
    "MO": ["Kansas City", "St. Louis", "Springfield", "Columbia", "Independence", "Lee's Summit", "O'Fallon", "St. Joseph", "St. Charles"],
    "MT": ["Billings", "Missoula", "Great Falls", "Bozeman", "Butte", "Helena", "Kalispell", "Havre", "Anaconda", "Miles City"],
    "NE": ["Omaha", "Lincoln", "Bellevue", "Grand Island", "Kearney", "Fremont", "Hastings", "Norfolk", "North Platte", "Columbus"],
    "NV": ["Las Vegas", "Henderson", "Reno", "North Las Vegas", "Sparks", "Carson City", "Fernley", "Elko", "Mesquite", "Boulder City"],
    "NH": ["Manchester", "Nashua", "Concord", "Derry", "Dover", "Rochester", "Salem", "Merrimack", "Hudson", "Londonderry"],
    "NJ": ["Newark", "Jersey City", "Paterson", "Elizabeth", "Edison", "Woodbridge", "Lakewood", "Toms River", "Hamilton", "Trenton"],
    "NM": ["Albuquerque", "Las Cruces", "Rio Rancho", "Santa Fe", "Roswell", "Farmington", "Clovis", "Hobbs", "Alamogordo", "Carlsbad"],
    "NY": ["New York City", "Buffalo", "Rochester", "Yonkers", "Albany", "Syracuse", "New Rochelle", "Mount Vernon", "Schenectady"],
    "NC": ["Charlotte", "Raleigh", "Greensboro", "Durham", "Winston-Salem", "Fayetteville", "Cary", "Wilmington", "High Point", "Asheville"],
    "ND": ["Fargo", "Bismarck", "Grand Forks", "Minot", "West Fargo", "Williston", "Dickinson", "Mandat", "Jamestown", "Wahpeton"],
    "OH": ["Columbus", "Cleveland", "Cincinnati", "Toledo", "Akron", "Dayton", "Parma", "Canton", "Youngstown", "Lorain"],
    "OK": ["Oklahoma City", "Tulsa", "Norman", "Broken Arrow", "Edmond", "Lawton", "Moore", "Midwest City", "Enid", "Stillwater"],
    "OR": ["Portland", "Salem", "Eugene", "Gresham", "Hillsboro", "Beaverton", "Bend", "Medford", "Springfield", "Corvallis"],
    "PA": ["Philadelphia", "Pittsburgh", "Allentown", "Erie", "Reading", "Scranton", "Bethlehem", "Lancaster", "Harrisburg", "Altoona"],
    "RI": ["Providence", "Warwick", "Cranston", "Pawtucket", "East Providence", "Woonsocket", "Coventry", "Cumberland", "Johnston"],
    "SC": ["Charleston", "Columbia", "North Charleston", "Mount Pleasant", "Rock Hill", "Greenville", "Summerville", "Goose Creek"],
    "SD": ["Sioux Falls", "Rapid City", "Aberdeen", "Brookings", "Watertown", "Mitchell", "Yankton", "Pierre", "Huron", "Spearfish"],
    "TN": ["Nashville", "Memphis", "Knoxville", "Chattanooga", "Clarksville", "Murfreesboro", "Franklin", "Jackson", "Johnson City"],
    "TX": ["Houston", "Dallas", "Austin", "San Antonio", "Fort Worth", "El Paso", "Arlington", "Corpus Christi", "Plano", "Laredo"],
    "UT": ["Salt Lake City", "West Valley City", "Provo", "West Jordan", "Orem", "Sandy", "Ogden", "St. George", "Layton", "Taylorsville"],
    "VT": ["Burlington", "South Burlington", "Rutland", "Barre", "Montpelier", "Winooski", "St. Albans", "Newport", "Vergennes"],
    "VA": ["Virginia Beach", "Norfolk", "Chesapeake", "Richmond", "Newport News", "Alexandria", "Hampton", "Roanoke", "Portsmouth"],
    "WA": ["Seattle", "Spokane", "Tacoma", "Vancouver", "Bellevue", "Kent", "Everett", "Renton", "Federal Way", "Yakima"],
    "WV": ["Charleston", "Huntington", "Morgantown", "Parkersburg", "Wheeling", "Weirton", "Fairmont", "Martinsburg", "Beckley"],
    "WI": ["Milwaukee", "Madison", "Green Bay", "Kenosha", "Racine", "Appleton", "Waukesha", "Eau Claire", "Oshkosh", "Janesville"],
    "WY": ["Cheyenne", "Casper", "Laramie", "Gillette", "Rock Springs", "Sheridan", "Green River", "Evanston", "Riverton", "Cody"]
}

def human_stealth_delay():
    """ Industrial Stealth Protocol: mandatory randomized delay. """
    time.sleep(random.uniform(5, 15))

def check_access(user, feature):
    """ Industrial access management logic. """
    if not user: return False
    if user.subscription_status in ['lifetime', 'monthly', 'weekly']:
        if user.subscription_status == 'lifetime' or (user.subscription_end and user.subscription_end > datetime.utcnow()):
            return True
    now = datetime.utcnow()
    trial_start = user.created_at
    if feature == 'email' and now < trial_start + timedelta(hours=24): return True
    if feature == 'ai' and now < trial_start + timedelta(hours=48): return True
    return False
