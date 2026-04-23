"""
Central configuration: target ZIPs, county-to-ZIP mappings, scraper settings.
"""

# All target ZIP codes grouped by market
TARGET_ZIPS = {
    "dallas": ["75210", "75216", "75217", "75232", "75215"],
    "houston": ["77026", "77028", "77033", "77021", "77012", "77003", "77051"],
    "austin": ["78721", "78724", "78744", "78745"],
    "san_antonio": ["78207", "78210", "78228", "78237"],
    "collin_county": ["75069", "75071", "75078"],
    "kaufman_county": ["75126", "75142", "75160", "75114"],
    "las_vegas": ["89121", "89122", "89104", "89101", "89030", "89031"],
    "phoenix": ["85041", "85043", "85009", "85033", "85035"],
    "albuquerque": ["87121", "87105"],
    "okc": ["73111", "73117", "73129"],
    "edmond": ["73013", "73034"],
    "tulsa": ["74110", "74112", "74106"],
    "yukon": ["73099"],
    "brevard": ["32935", "32907", "32955", "32940"],
    "port_st_lucie": ["34953", "34983", "34984"],
    "gainesville": ["32641", "32607", "32609"],
    "fayetteville_nc": ["28314", "28311", "28306"],
    "gastonia": ["28052", "28054"],
    "asheville": ["28801", "28806"],
    "clarksville": ["37042", "37040"],
    "knoxville": ["37914", "37921"],
    "richmond": ["23223", "23231", "23224"],
    "south_carolina": ["29203", "29611"],
    "columbus_ga": ["31903", "31906"],
    "bossier_city": ["71111", "71112"],
    "shreveport": ["71108", "71109", "71107"],
    "detroit": ["48205", "48224", "48228"],
    "indianapolis": ["46218", "46222", "46201"],
    "columbus_oh": ["43207", "43223", "43211"],
    "dayton": ["45417", "45405"],
    "toledo": ["43609", "43615"],
    "louisville": ["40210", "40211", "40212"],
    "reading": ["19601", "19602"],
    "manchester": ["03103"],
    "fresno": ["93706", "93702", "93727"],
}

# Flat set of all target ZIPs for fast lookup
ALL_ZIPS = set(z for zips in TARGET_ZIPS.values() for z in zips)

# Maps each ZIP to its county + state (used for routing scrapers and Neo4j)
ZIP_COUNTY_MAP = {
    # Dallas County, TX
    "75210": {"county": "Dallas", "city": "Dallas", "state": "TX"},
    "75216": {"county": "Dallas", "city": "Dallas", "state": "TX"},
    "75217": {"county": "Dallas", "city": "Dallas", "state": "TX"},
    "75232": {"county": "Dallas", "city": "Dallas", "state": "TX"},
    "75215": {"county": "Dallas", "city": "Dallas", "state": "TX"},
    # Harris County, TX
    "77026": {"county": "Harris", "city": "Houston", "state": "TX"},
    "77028": {"county": "Harris", "city": "Houston", "state": "TX"},
    "77033": {"county": "Harris", "city": "Houston", "state": "TX"},
    "77021": {"county": "Harris", "city": "Houston", "state": "TX"},
    "77012": {"county": "Harris", "city": "Houston", "state": "TX"},
    "77003": {"county": "Harris", "city": "Houston", "state": "TX"},
    "77051": {"county": "Harris", "city": "Houston", "state": "TX"},
    # Travis County, TX (Austin)
    "78721": {"county": "Travis", "city": "Austin", "state": "TX"},
    "78724": {"county": "Travis", "city": "Austin", "state": "TX"},
    "78744": {"county": "Travis", "city": "Austin", "state": "TX"},
    "78745": {"county": "Travis", "city": "Austin", "state": "TX"},
    # Bexar County, TX (San Antonio)
    "78207": {"county": "Bexar", "city": "San Antonio", "state": "TX"},
    "78210": {"county": "Bexar", "city": "San Antonio", "state": "TX"},
    "78228": {"county": "Bexar", "city": "San Antonio", "state": "TX"},
    "78237": {"county": "Bexar", "city": "San Antonio", "state": "TX"},
    # Collin County, TX
    "75069": {"county": "Collin", "city": "McKinney", "state": "TX"},
    "75071": {"county": "Collin", "city": "McKinney", "state": "TX"},
    "75078": {"county": "Collin", "city": "Prosper", "state": "TX"},
    # Kaufman County, TX
    "75126": {"county": "Kaufman", "city": "Forney", "state": "TX"},
    "75142": {"county": "Kaufman", "city": "Kaufman", "state": "TX"},
    "75160": {"county": "Kaufman", "city": "Terrell", "state": "TX"},
    "75114": {"county": "Kaufman", "city": "Crandall", "state": "TX"},
    # Clark County, NV (Las Vegas)
    "89121": {"county": "Clark", "city": "Las Vegas", "state": "NV"},
    "89122": {"county": "Clark", "city": "Las Vegas", "state": "NV"},
    "89104": {"county": "Clark", "city": "Las Vegas", "state": "NV"},
    "89101": {"county": "Clark", "city": "Las Vegas", "state": "NV"},
    "89030": {"county": "Clark", "city": "North Las Vegas", "state": "NV"},
    "89031": {"county": "Clark", "city": "North Las Vegas", "state": "NV"},
    # Maricopa County, AZ (Phoenix)
    "85041": {"county": "Maricopa", "city": "Phoenix", "state": "AZ"},
    "85043": {"county": "Maricopa", "city": "Phoenix", "state": "AZ"},
    "85009": {"county": "Maricopa", "city": "Phoenix", "state": "AZ"},
    "85033": {"county": "Maricopa", "city": "Phoenix", "state": "AZ"},
    "85035": {"county": "Maricopa", "city": "Phoenix", "state": "AZ"},
    # Bernalillo County, NM (Albuquerque)
    "87121": {"county": "Bernalillo", "city": "Albuquerque", "state": "NM"},
    "87105": {"county": "Bernalillo", "city": "Albuquerque", "state": "NM"},
    # Oklahoma County, OK (OKC)
    "73111": {"county": "Oklahoma", "city": "Oklahoma City", "state": "OK"},
    "73117": {"county": "Oklahoma", "city": "Oklahoma City", "state": "OK"},
    "73129": {"county": "Oklahoma", "city": "Oklahoma City", "state": "OK"},
    # Oklahoma County, OK (Edmond)
    "73013": {"county": "Oklahoma", "city": "Edmond", "state": "OK"},
    "73034": {"county": "Oklahoma", "city": "Edmond", "state": "OK"},
    # Tulsa County, OK
    "74110": {"county": "Tulsa", "city": "Tulsa", "state": "OK"},
    "74112": {"county": "Tulsa", "city": "Tulsa", "state": "OK"},
    "74106": {"county": "Tulsa", "city": "Tulsa", "state": "OK"},
    # Canadian County, OK (Yukon)
    "73099": {"county": "Canadian", "city": "Yukon", "state": "OK"},
    # Brevard County, FL
    "32935": {"county": "Brevard", "city": "Melbourne", "state": "FL"},
    "32907": {"county": "Brevard", "city": "Palm Bay", "state": "FL"},
    "32955": {"county": "Brevard", "city": "Rockledge", "state": "FL"},
    "32940": {"county": "Brevard", "city": "Melbourne", "state": "FL"},
    # St. Lucie County, FL
    "34953": {"county": "St. Lucie", "city": "Port St. Lucie", "state": "FL"},
    "34983": {"county": "St. Lucie", "city": "Port St. Lucie", "state": "FL"},
    "34984": {"county": "St. Lucie", "city": "Port St. Lucie", "state": "FL"},
    # Alachua County, FL (Gainesville)
    "32641": {"county": "Alachua", "city": "Gainesville", "state": "FL"},
    "32607": {"county": "Alachua", "city": "Gainesville", "state": "FL"},
    "32609": {"county": "Alachua", "city": "Gainesville", "state": "FL"},
    # Cumberland County, NC (Fayetteville)
    "28314": {"county": "Cumberland", "city": "Fayetteville", "state": "NC"},
    "28311": {"county": "Cumberland", "city": "Fayetteville", "state": "NC"},
    "28306": {"county": "Cumberland", "city": "Fayetteville", "state": "NC"},
    # Gaston County, NC
    "28052": {"county": "Gaston", "city": "Gastonia", "state": "NC"},
    "28054": {"county": "Gaston", "city": "Gastonia", "state": "NC"},
    # Buncombe County, NC (Asheville)
    "28801": {"county": "Buncombe", "city": "Asheville", "state": "NC"},
    "28806": {"county": "Buncombe", "city": "Asheville", "state": "NC"},
    # Montgomery County, TN (Clarksville)
    "37042": {"county": "Montgomery", "city": "Clarksville", "state": "TN"},
    "37040": {"county": "Montgomery", "city": "Clarksville", "state": "TN"},
    # Knox County, TN (Knoxville)
    "37914": {"county": "Knox", "city": "Knoxville", "state": "TN"},
    "37921": {"county": "Knox", "city": "Knoxville", "state": "TN"},
    # Richmond City, VA
    "23223": {"county": "Richmond City", "city": "Richmond", "state": "VA"},
    "23231": {"county": "Richmond City", "city": "Richmond", "state": "VA"},
    "23224": {"county": "Richmond City", "city": "Richmond", "state": "VA"},
    # South Carolina
    "29203": {"county": "Richland", "city": "Columbia", "state": "SC"},
    "29611": {"county": "Greenville", "city": "Greenville", "state": "SC"},
    # Muscogee County, GA (Columbus)
    "31903": {"county": "Muscogee", "city": "Columbus", "state": "GA"},
    "31906": {"county": "Muscogee", "city": "Columbus", "state": "GA"},
    # Bossier Parish, LA
    "71111": {"county": "Bossier", "city": "Bossier City", "state": "LA"},
    "71112": {"county": "Bossier", "city": "Bossier City", "state": "LA"},
    # Caddo Parish, LA (Shreveport)
    "71108": {"county": "Caddo", "city": "Shreveport", "state": "LA"},
    "71109": {"county": "Caddo", "city": "Shreveport", "state": "LA"},
    "71107": {"county": "Caddo", "city": "Shreveport", "state": "LA"},
    # Wayne County, MI (Detroit)
    "48205": {"county": "Wayne", "city": "Detroit", "state": "MI"},
    "48224": {"county": "Wayne", "city": "Detroit", "state": "MI"},
    "48228": {"county": "Wayne", "city": "Detroit", "state": "MI"},
    # Marion County, IN (Indianapolis)
    "46218": {"county": "Marion", "city": "Indianapolis", "state": "IN"},
    "46222": {"county": "Marion", "city": "Indianapolis", "state": "IN"},
    "46201": {"county": "Marion", "city": "Indianapolis", "state": "IN"},
    # Franklin County, OH (Columbus)
    "43207": {"county": "Franklin", "city": "Columbus", "state": "OH"},
    "43223": {"county": "Franklin", "city": "Columbus", "state": "OH"},
    "43211": {"county": "Franklin", "city": "Columbus", "state": "OH"},
    # Montgomery County, OH (Dayton)
    "45417": {"county": "Montgomery", "city": "Dayton", "state": "OH"},
    "45405": {"county": "Montgomery", "city": "Dayton", "state": "OH"},
    # Lucas County, OH (Toledo)
    "43609": {"county": "Lucas", "city": "Toledo", "state": "OH"},
    "43615": {"county": "Lucas", "city": "Toledo", "state": "OH"},
    # Jefferson County, KY (Louisville)
    "40210": {"county": "Jefferson", "city": "Louisville", "state": "KY"},
    "40211": {"county": "Jefferson", "city": "Louisville", "state": "KY"},
    "40212": {"county": "Jefferson", "city": "Louisville", "state": "KY"},
    # Berks County, PA (Reading)
    "19601": {"county": "Berks", "city": "Reading", "state": "PA"},
    "19602": {"county": "Berks", "city": "Reading", "state": "PA"},
    # Hillsborough County, NH (Manchester)
    "03103": {"county": "Hillsborough", "city": "Manchester", "state": "NH"},
    # Fresno County, CA
    "93706": {"county": "Fresno", "city": "Fresno", "state": "CA"},
    "93702": {"county": "Fresno", "city": "Fresno", "state": "CA"},
    "93727": {"county": "Fresno", "city": "Fresno", "state": "CA"},
}

# Adjacent ZIP lookups for buyer matching (each ZIP maps to its neighbors)
# Populated at runtime by the matcher using geographic proximity
ADJACENT_ZIPS = {}

# Scraper behavior settings
SCRAPER_SETTINGS = {
    "request_delay_min": 2.0,   # seconds between requests
    "request_delay_max": 3.5,
    "max_retries": 3,
    "retry_backoff": 2.0,       # seconds; doubles each retry
    "timeout": 30,
    "user_agents": [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ],
}

# Land use codes that indicate vacant/infill parcels (varies by CAD)
VACANT_LAND_USE_CODES = {
    "TX": ["A1", "A2", "B1", "B2", "C1", "C2", "D1", "D2", "E"],  # PTAD categories
    "generic_vacant": ["vacant", "unimproved", "idle", "land only", "0100", "1000", "V"],
}

# Buyer type classification keywords
BUYER_TYPE_KEYWORDS = {
    "builder": ["homes", "builder", "construction", "development", "dev ", "builds", "constructors"],
    "flipper": ["invest", "properties llc", "holdings", "acquisitions", "capital", "assets", "ventures"],
    "landlord": ["rentals", "rental", "property management", "pm llc", "leasing"],
    "land_banker": ["land", "acres", "lots llc", "lot invest", "land bank"],
    "note_buyer": ["mortgage", "note", "fund", "financial", "lending", "capital fund"],
}

# Distress score weights (used when computing property distress score 1-10)
DISTRESS_WEIGHTS = {
    "tax_delinquent": 3,
    "preforeclosure": 3,
    "nod": 3,
    "bankruptcy": 2,
    "code_violation": 2,
    "probate": 2,
    "absentee_owner": 1,
    "dom90": 1,
    "vacant_land": 1,
    "ghost_plat": 1,
}
