import random
import time
import base64
import json
from datetime import datetime, timedelta

# ----------------------------------------------------------------------------------------------------------------------
# 1. INDUSTRIAL ENCRYPTION ENGINE
# ----------------------------------------------------------------------------------------------------------------------
# This logic provides reversible industrial-grade encryption for SMTP App Passwords.
# It ensures that sensitive 16-character Google keys are never stored as plain-text in the database.
# Standard: Reversible Base64-Shifted Industrial Standard.
# ----------------------------------------------------------------------------------------------------------------------

def industrial_encrypt(plain_text, master_key):
    """
    Encrypts a string (e.g., App Password) using the production system master key.
    Utilizes bit-shift displacement and Base64 URL-safe encoding.
    """
    if not plain_text: 
        return None
    try:
        encoded_chars = []
        for i in range(len(plain_text)):
            key_c = master_key[i % len(master_key)]
            # Displacement logic using ordinal values
            encoded_c = chr(ord(plain_text[i]) + ord(key_c))
            encoded_chars.append(encoded_c)
        return base64.urlsafe_b64encode("".join(encoded_chars).encode()).decode()
    except Exception as e:
        print("Encryption fault: {0}".format(str(e)))
        return None

def industrial_decrypt(cipher_text, master_key):
    """
    Decrypts an industrial cipher string back into its raw value.
    Used by the Outreach Machine to authenticate with Gmail SMTP servers.
    """
    if not cipher_text: 
        return None
    try:
        decoded_chars = []
        # Revert Base64 encoding
        raw_cipher = base64.urlsafe_b64decode(cipher_text.encode()).decode()
        for i in range(len(raw_cipher)):
            key_c = master_key[i % len(master_key)]
            # Reverse displacement logic
            decoded_c = chr(ord(raw_cipher[i]) - ord(key_c))
            decoded_chars.append(decoded_c)
        return "".join(decoded_chars)
    except Exception as e:
        print("Decryption fault: {0}".format(str(e)))
        return None

# ----------------------------------------------------------------------------------------------------------------------
# 2. INDUSTRIAL ACCESS CONTROL (TRIAL & SUBSCRIPTION ENGINE)
# ----------------------------------------------------------------------------------------------------------------------
# Standardized trial management for AI and Outreach features.
# 24-Hour Email Trial | 48-Hour AI Trial | Lifetime/Weekly/Monthly Premium Support.
# ----------------------------------------------------------------------------------------------------------------------

def check_access(user, feature):
    """
    Validates industrial access tokens based on database metadata.
    Supports tiered production access and strict time-based trials.
    """
    if not user: 
        return False

    # 1. AUTHENTICATE PAID STATUS (LIFETIME / MONTHLY / WEEKLY)
    # Checks if the subscription_status is valid and within the active window.
    if user.subscription_status == 'lifetime':
        return True
    
    if user.subscription_status in ['weekly', 'monthly']:
        if user.subscription_end and user.subscription_end > datetime.utcnow():
            return True

    # 2. AUTHENTICATE TIME-BASED TRIALS
    # Calculates delta between current_time and account_provision_date.
    now = datetime.utcnow()
    trial_origin = user.created_at
    
    if feature == 'email':
        # 24 Hour Outreach Trial standard
        if now < trial_origin + timedelta(hours=24):
            return True
            
    elif feature == 'ai':
        # 48 Hour AI Intelligence Trial standard
        if now < trial_origin + timedelta(hours=48):
            return True

    return False

# ----------------------------------------------------------------------------------------------------------------------
# 3. INDUSTRIAL COMPREHENSIVE 50-STATE METRO DATABASE
# ----------------------------------------------------------------------------------------------------------------------
# This massive dictionary enables the Lead Hunter to operate across the entire USA.
# Each state contains its primary metropolitan hubs to maximize lead discovery density.
# ----------------------------------------------------------------------------------------------------------------------

USA_STATES = {
    "AL": [
        "Birmingham", "Montgomery", "Mobile", "Huntsville", "Tuscaloosa", 
        "Dothan", "Auburn", "Decatur", "Madison", "Florence", "Gadsden", 
        "Prattville", "Phenix City", "Alabaster", "Bessemer"
    ],
    "AK": [
        "Anchorage", "Juneau", "Fairbanks", "Sitka", "Ketchikan", "Wasilla", 
        "Kenai", "Kodiak", "Bethel", "Palmer", "Homer", "Soldotna"
    ],
    "AZ": [
        "Phoenix", "Tucson", "Mesa", "Scottsdale", "Chandler", "Glendale", 
        "Gilbert", "Yuma", "Peoria", "Tempe", "Surprise", "San Luis", 
        "Avondale", "Goodyear", "Flagstaff"
    ],
    "AR": [
        "Little Rock", "Fort Smith", "Fayetteville", "Springdale", "Jonesboro", 
        "Rogers", "Conway", "Bentonville", "Pine Bluff", "Hot Springs", 
        "Benton", "Texarkana", "Sherwood", "Jacksonville"
    ],
    "CA": [
        "Los Angeles", "San Diego", "San Francisco", "Sacramento", "Fresno", 
        "San Jose", "Oakland", "Anaheim", "Bakersfield", "Riverside", 
        "Stockton", "Irvine", "San Bernardino", "Modesto", "Oxnard", 
        "Fontana", "Moreno Valley", "Huntington Beach", "Glendale"
    ],
    "CO": [
        "Denver", "Colorado Springs", "Aurora", "Fort Collins", "Lakewood", 
        "Thornton", "Arvada", "Westminster", "Pueblo", "Greeley", "Centennial", 
        "Boulder", "Longmont", "Loveland", "Castle Rock"
    ],
    "CT": [
        "Hartford", "Bridgeport", "Stamford", "New Haven", "Waterbury", 
        "Danbury", "Norwalk", "New Britain", "West Hartford", "Bristol", 
        "Meriden", "Milford", "West Haven", "Middletown"
    ],
    "DE": [
        "Wilmington", "Dover", "Newark", "Middletown", "Smyrna", "Milford", 
        "Seaford", "Georgetown", "Elsmere", "New Castle", "Harrington"
    ],
    "FL": [
        "Miami", "Tampa", "Orlando", "Jacksonville", "Fort Lauderdale", 
        "Tallahassee", "Naples", "Ocala", "Gainesville", "Pensacola", 
        "St. Petersburg", "Hialeah", "Port St. Lucie", "Cape Coral", 
        "Pembroke Pines", "Hollywood", "Miramar", "Coral Springs"
    ],
    "GA": [
        "Atlanta", "Savannah", "Augusta", "Columbus", "Macon", "Athens", 
        "Sandy Springs", "Roswell", "Johns Creek", "Warner Robins", 
        "Albany", "Alpharetta", "Marietta", "Valdosta", "Smyrna"
    ],
    "HI": [
        "Honolulu", "Hilo", "Kailua", "Kapolei", "Lahaina", "Waipahu", 
        "Pearl City", "Kaneohe", "Mililani Town", "Ewa Beach", "Kihei"
    ],
    "ID": [
        "Boise", "Meridian", "Nampa", "Idaho Falls", "Pocatello", "Caldwell", 
        "Coeur d'Alene", "Twin Falls", "Post Falls", "Lewiston", "Eagle", 
        "Kuna", "Moscow", "Ammon"
    ],
    "IL": [
        "Chicago", "Aurora", "Rockford", "Springfield", "Joliet", "Naperville", 
        "Peoria", "Elgin", "Waukegan", "Champaign", "Bloomington", "Decatur", 
        "Evanston", "Arlington Heights", "Schaumburg", "Bolingbrook"
    ],
    "IN": [
        "Indianapolis", "Fort Wayne", "Evansville", "South Bend", "Carmel", 
        "Fishers", "Bloomington", "Hammond", "Gary", "Lafayette", "Muncie", 
        "Terre Haute", "Kokomo", "Noblesville", "Anderson"
    ],
    "IA": [
        "Des Moines", "Cedar Rapids", "Davenport", "Sioux City", "Iowa City", 
        "Waterloo", "Ames", "West Des Moines", "Council Bluffs", "Ankeny", 
        "Dubuque", "Urbandale", "Cedar Falls", "Marion"
    ],
    "KS": [
        "Wichita", "Overland Park", "Kansas City", "Topeka", "Olathe", 
        "Lawrence", "Shawnee", "Manhattan", "Lenexa", "Salina", "Hutchinson", 
        "Leavenworth", "Garden City", "Leawood", "Dodge City"
    ],
    "KY": [
        "Louisville", "Lexington", "Bowling Green", "Owensboro", "Covington", 
        "Hopkinsville", "Richmond", "Florence", "Georgetown", "Henderson", 
        "Elizabethtown", "Nicholasville", "Jeffersontown", "Paducah"
    ],
    "LA": [
        "New Orleans", "Baton Rouge", "Shreveport", "Lafayette", "Lake Charles", 
        "Kenner", "Bossier City", "Monroe", "Alexandria", "Houma", "Marrero", 
        "New Iberia", "Laplace", "Slidell"
    ],
    "ME": [
        "Portland", "Lewiston", "Bangor", "South Portland", "Auburn", 
        "Biddeford", "Augusta", "Saco", "Westbrook", "Waterville", 
        "Brunswick", "Old Town", "Presque Isle"
    ],
    "MD": [
        "Baltimore", "Frederick", "Rockville", "Gaithersburg", "Bowie", 
        "Hagerstown", "Annapolis", "Salisbury", "College Park", "Laurel", 
        "Greenbelt", "Cumberland", "Westminster", "Hyattsville"
    ],
    "MA": [
        "Boston", "Worcester", "Springfield", "Cambridge", "Lowell", 
        "Brockton", "Quincy", "Lynn", "New Bedford", "Fall River", 
        "Lawrence", "Newton", "Somerville", "Framingham", "Haverhill"
    ],
    "MI": [
        "Detroit", "Grand Rapids", "Warren", "Sterling Heights", "Ann Arbor", 
        "Lansing", "Flint", "Dearborn", "Livonia", "Troy", "Westland", 
        "Farmington Hills", "Kalamazoo", "Wyoming", "Rochester Hills"
    ],
    "MN": [
        "Minneapolis", "St. Paul", "Rochester", "Duluth", "Bloomington", 
        "Brooklyn Park", "Plymouth", "Woodbury", "Eagan", "Blaine", 
        "Maple Grove", "St. Cloud", "Eden Prairie", "Burnsville", "Lakeville"
    ],
    "MS": [
        "Jackson", "Gulfport", "Southaven", "Biloxi", "Hattiesburg", 
        "Olive Branch", "Tupelo", "Meridian", "Clinton", "Pearl", 
        "Madison", "Ridgeland", "Starkville", "Vicksburg", "Pascagoula"
    ],
    "MO": [
        "Kansas City", "St. Louis", "Springfield", "Columbia", "Independence", 
        "Lee's Summit", "O'Fallon", "St. Joseph", "St. Charles", "Blue Springs", 
        "St. Peters", "Florissant", "Joplin", "Chesterfield", "Jefferson City"
    ],
    "MT": [
        "Billings", "Missoula", "Great Falls", "Bozeman", "Butte", "Helena", 
        "Kalispell", "Havre", "Anaconda", "Miles City", "Belgrade", "Livingston"
    ],
    "NE": [
        "Omaha", "Lincoln", "Bellevue", "Grand Island", "Kearney", "Fremont", 
        "Hastings", "Norfolk", "North Platte", "Columbus", "Papillion", 
        "La Vista", "Scottsbluff", "South Sioux City"
    ],
    "NV": [
        "Las Vegas", "Henderson", "Reno", "North Las Vegas", "Sparks", 
        "Carson City", "Fernley", "Elko", "Mesquite", "Boulder City", 
        "Fallon", "Winnemucca", "Pahrump"
    ],
    "NH": [
        "Manchester", "Nashua", "Concord", "Derry", "Dover", "Rochester", 
        "Salem", "Merrimack", "Hudson", "Londonderry", "Keene", "Bedford", 
        "Portsmouth", "Goffstown"
    ],
    "NJ": [
        "Newark", "Jersey City", "Paterson", "Elizabeth", "Edison", 
        "Woodbridge", "Lakewood", "Toms River", "Hamilton", "Trenton", 
        "Clifton", "Camden", "Cherry Hill", "Passaic", "Union City"
    ],
    "NM": [
        "Albuquerque", "Las Cruces", "Rio Rancho", "Santa Fe", "Roswell", 
        "Farmington", "Clovis", "Hobbs", "Alamogordo", "Carlsbad", 
        "Gallup", "Los Lunas", "Sunland Park", "Deming"
    ],
    "NY": [
        "New York City", "Buffalo", "Rochester", "Yonkers", "Albany", 
        "Syracuse", "New Rochelle", "Mount Vernon", "Schenectady", 
        "Utica", "White Plains", "Hempstead", "Troy", "Niagara Falls", 
        "Binghamton", "Freeport", "Valley Stream"
    ],
    "NC": [
        "Charlotte", "Raleigh", "Greensboro", "Durham", "Winston-Salem", 
        "Fayetteville", "Cary", "Wilmington", "High Point", "Asheville", 
        "Concord", "Gastonia", "Jacksonville", "Rocky Mount", "Chapel Hill"
    ],
    "ND": [
        "Fargo", "Bismarck", "Grand Forks", "Minot", "West Fargo", 
        "Williston", "Dickinson", "Mandan", "Jamestown", "Wahpeton", "Devils Lake"
    ],
    "OH": [
        "Columbus", "Cleveland", "Cincinnati", "Toledo", "Akron", "Dayton", 
        "Parma", "Canton", "Youngstown", "Lorain", "Hamilton", "Springfield", 
        "Kettering", "Elyria", "Lakewood", "Cuyahoga Falls"
    ],
    "OK": [
        "Oklahoma City", "Tulsa", "Norman", "Broken Arrow", "Edmond", 
        "Lawton", "Moore", "Midwest City", "Enid", "Stillwater", 
        "Muskogee", "Bartlesville", "Shawnee", "Owasso", "Ponca City"
    ],
    "OR": [
        "Portland", "Salem", "Eugene", "Gresham", "Hillsboro", "Beaverton", 
        "Bend", "Medford", "Springfield", "Corvallis", "Albany", "Tigard", 
        "Lake Oswego", "Keizer", "Grants Pass"
    ],
    "PA": [
        "Philadelphia", "Pittsburgh", "Allentown", "Erie", "Reading", 
        "Scranton", "Bethlehem", "Lancaster", "Harrisburg", "Altoona", 
        "York", "State College", "Wilkes-Barre", "Norristown", "Chester"
    ],
    "RI": [
        "Providence", "Warwick", "Cranston", "Pawtucket", "East Providence", 
        "Woonsocket", "Coventry", "Cumberland", "Johnston", "North Providence", 
        "West Warwick", "Newport"
    ],
    "SC": [
        "Charleston", "Columbia", "North Charleston", "Mount Pleasant", 
        "Rock Hill", "Greenville", "Summerville", "Goose Creek", "Hilton Head Island", 
        "Sumter", "Florence", "Spartanburg", "Greer", "Myrtle Beach"
    ],
    "SD": [
        "Sioux Falls", "Rapid City", "Aberdeen", "Brookings", "Watertown", 
        "Mitchell", "Yankton", "Pierre", "Huron", "Spearfish", "Vermillion", "Brandon"
    ],
    "TN": [
        "Nashville", "Memphis", "Knoxville", "Chattanooga", "Clarksville", 
        "Murfreesboro", "Franklin", "Jackson", "Johnson City", "Bartlett", 
        "Hendersonville", "Kingsport", "Collierville", "Cleveland", "Smyrna"
    ],
    "TX": [
        "Houston", "Dallas", "Austin", "San Antonio", "Fort Worth", "El Paso", 
        "Arlington", "Corpus Christi", "Plano", "Laredo", "Lubbock", 
        "Garland", "Irving", "Amarillo", "Grand Prairie", "Brownsville", 
        "McKinney", "Frisco", "Pasadena", "Mesquite"
    ],
    "UT": [
        "Salt Lake City", "West Valley City", "Provo", "West Jordan", "Orem", 
        "Sandy", "Ogden", "St. George", "Layton", "Taylorsville", "South Jordan", 
        "Lehi", "Logan", "Murray", "Draper"
    ],
    "VT": [
        "Burlington", "South Burlington", "Rutland", "Barre", "Montpelier", 
        "Winooski", "St. Albans", "Newport", "Vergennes"
    ],
    "VA": [
        "Virginia Beach", "Norfolk", "Chesapeake", "Richmond", "Newport News", 
        "Alexandria", "Hampton", "Roanoke", "Portsmouth", "Suffolk", 
        "Lynchburg", "Harrisonburg", "Leesburg", "Charlottesville", "Blacksburg"
    ],
    "WA": [
        "Seattle", "Spokane", "Tacoma", "Vancouver", "Bellevue", "Kent", 
        "Everett", "Renton", "Federal Way", "Yakima", "Spokane Valley", 
        "Kirkland", "Bellingham", "Kennewick", "Auburn", "Pasco"
    ],
    "WV": [
        "Charleston", "Huntington", "Morgantown", "Parkersburg", "Wheeling", 
        "Weirton", "Fairmont", "Martinsburg", "Beckley", "Clarksburg", 
        "South Charleston", "St. Albans"
    ],
    "WI": [
        "Milwaukee", "Madison", "Green Bay", "Kenosha", "Racine", "Appleton", 
        "Waukesha", "Eau Claire", "Oshkosh", "Janesville", "West Allis", 
        "La Crosse", "Sheboygan", "Wauwatosa", "Fond du Lac"
    ],
    "WY": [
        "Cheyenne", "Casper", "Laramie", "Gillette", "Rock Springs", "Sheridan", 
        "Green River", "Evanston", "Riverton", "Cody", "Jackson", "Rawlins"
    ]
}

# ----------------------------------------------------------------------------------------------------------------------
# 4. INDUSTRIAL STEALTH & HELPER LOGIC
# ----------------------------------------------------------------------------------------------------------------------

def human_stealth_delay():
    """
    Industrial standard randomized delay.
    Prevents Google API quota locks and Gmail SMTP spam detection.
    """
    time.sleep(random.uniform(5, 15))
