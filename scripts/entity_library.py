"""
entity_library.py -- Entity-first SEO library for all 14 niches.

Each niche has:
  - 10-15 entities with @type, sameAs (Wikipedia), wikidata QID
  - Semantic relationships (subject-verb-object triples)
  - Fuzzy matching for content scanning (plurals, hyphens, variants)
  - Keyword-to-entity targeting for article-specific guidance

Used by:
  - article_template.py: entity prompt injection + JSON-LD schema
  - article_enhancer.py: entity coverage check + injection
  - article_qa.py: entity scoring (coverage, density, salience)
  - keyword_researcher.py: keyword-entity tagging
"""

import re
from collections import defaultdict

# Entity format: {name: {"@type": schema_type, "sameAs": wikipedia_url, "wikidata": qid_url}}

NICHE_ENTITIES = {
    "dog-comfort": {
        "memory foam": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Memory_foam", "wikidata": "https://www.wikidata.org/entity/Q1054971"},
        "arthritis": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Arthritis", "wikidata": "https://www.wikidata.org/entity/Q8356"},
        "hip dysplasia": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Hip_dysplasia_(canine)", "wikidata": "https://www.wikidata.org/entity/Q1618082"},
        "separation anxiety": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Separation_anxiety_in_dogs", "wikidata": "https://www.wikidata.org/entity/Q7451171"},
        "crate training": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Crate_training", "wikidata": "https://www.wikidata.org/entity/Q5182282"},
        "orthopedic bed": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Orthopedic_mattress", "wikidata": "https://www.wikidata.org/entity/Q85802974"},
        "golden retriever": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Golden_Retriever", "wikidata": "https://www.wikidata.org/entity/Q38469"},
        "german shepherd": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/German_Shepherd", "wikidata": "https://www.wikidata.org/entity/Q5765"},
        "labrador retriever": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Labrador_Retriever", "wikidata": "https://www.wikidata.org/entity/Q39816"},
        "french bulldog": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/French_Bulldog", "wikidata": "https://www.wikidata.org/entity/Q65063"},
        "polyester fiber": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Polyester", "wikidata": "https://www.wikidata.org/entity/Q188245"},
        "enzyme cleaner": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Enzymatic_cleaner", "wikidata": "https://www.wikidata.org/entity/Q11975135"},
    },
    "camping-gear": {
        "sleeping bag": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Sleeping_bag", "wikidata": "https://www.wikidata.org/entity/Q214638"},
        "tent": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Tent", "wikidata": "https://www.wikidata.org/entity/Q170544"},
        "backpacking": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Backpacking_(wilderness)", "wikidata": "https://www.wikidata.org/entity/Q12014173"},
        "Gore-Tex": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Gore-Tex", "wikidata": "https://www.wikidata.org/entity/Q867068"},
        "hypothermia": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Hypothermia", "wikidata": "https://www.wikidata.org/entity/Q1036696"},
        "camping stove": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Portable_stove", "wikidata": "https://www.wikidata.org/entity/Q616204"},
        "down feather": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Down_feather", "wikidata": "https://www.wikidata.org/entity/Q953515"},
        "ultralight backpacking": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Ultralight_backpacking", "wikidata": "https://www.wikidata.org/entity/Q1372142"},
        "water purification": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Water_purification", "wikidata": "https://www.wikidata.org/entity/Q1463025"},
        "Leave No Trace": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Leave_No_Trace", "wikidata": "https://www.wikidata.org/entity/Q559348"},
        "National Park Service": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/National_Park_Service", "wikidata": "https://www.wikidata.org/entity/Q308439"},
        "Mountain Safety Research": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Mountain_Safety_Research", "wikidata": "https://www.wikidata.org/entity/Q10589790"},
        "merino": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Merino", "wikidata": "https://www.wikidata.org/entity/Q651765"},
        "frostbite": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Frostbite", "wikidata": "https://www.wikidata.org/entity/Q1350326"},
        "ASTM International": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/ASTM_International", "wikidata": "https://www.wikidata.org/entity/Q621977"},
    },
    "cat-care": {
        "cat litter": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Cat_litter", "wikidata": "https://www.wikidata.org/entity/Q115959335"},
        "cat scratching post": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Scratching_post", "wikidata": "https://www.wikidata.org/entity/Q1412123"},
        "feline lower urinary tract disease": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Feline_lower_urinary_tract_disease", "wikidata": "https://www.wikidata.org/entity/Q538309"},
        "toxoplasmosis": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Toxoplasmosis", "wikidata": "https://www.wikidata.org/entity/Q154878"},
        "hairball": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Hairball", "wikidata": "https://www.wikidata.org/entity/Q2360566"},
        "catnip": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Nepeta_cataria", "wikidata": "https://www.wikidata.org/entity/Q161139"},
        "cat tree": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Cat_tree", "wikidata": "https://www.wikidata.org/entity/Q1014401"},
        "Persian cat": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Persian_cat", "wikidata": "https://www.wikidata.org/entity/Q42610"},
        "Maine Coon": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Maine_Coon", "wikidata": "https://www.wikidata.org/entity/Q42659"},
        "Siamese cat": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Siamese_cat", "wikidata": "https://www.wikidata.org/entity/Q42604"},
        "taurine": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Taurine", "wikidata": "https://www.wikidata.org/entity/Q207051"},
        "AAFCO": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Association_of_American_Feed_Control_Officials", "wikidata": "https://www.wikidata.org/entity/Q104840735"},
        "bentonite": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Bentonite", "wikidata": "https://www.wikidata.org/entity/Q380149"},
        "chronic kidney disease": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Chronic_kidney_disease", "wikidata": "https://www.wikidata.org/entity/Q736715"},
        "feline panleukopenia": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Feline_panleukopenia", "wikidata": "https://www.wikidata.org/entity/Q18975615"},
    },
    "home-coffee": {
        "espresso": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Espresso"},
        "espresso machine": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Espresso_machine", "wikidata": "https://www.wikidata.org/entity/Q1164104"},
        "Moka pot": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Moka_pot", "wikidata": "https://www.wikidata.org/entity/Q152433"},
        "French press": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/French_press"},
        "pour-over coffee": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Drip_brewing"},
        "paper coffee filter": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Coffee_filter", "wikidata": "https://www.wikidata.org/entity/Q1106847"},
        "coffee grinder": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Coffee_grinder"},
        "Arabica coffee": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Coffea_arabica"},
        "Robusta coffee": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Coffea_canephora"},
        "cold brew": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Cold_brew_coffee"},
        "caffeine": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Caffeine"},
        "chlorogenic acid": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Chlorogenic_acid", "wikidata": "https://www.wikidata.org/entity/Q412431"},
        "gastroesophageal reflux disease": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Gastroesophageal_reflux_disease", "wikidata": "https://www.wikidata.org/entity/Q273181"},
        "insomnia": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Insomnia", "wikidata": "https://www.wikidata.org/entity/Q11139"},
        "descaling": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Descaling"},
        "barista": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Barista"},
        "Specialty Coffee Association": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Specialty_Coffee_Association"},
        "International Coffee Organization": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/International_Coffee_Organization", "wikidata": "https://www.wikidata.org/entity/Q1666427"},
        "Food and Drug Administration": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Food_and_Drug_Administration", "wikidata": "https://www.wikidata.org/entity/Q204711"},
        "National Coffee Association": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/National_Coffee_Association", "wikidata": "https://www.wikidata.org/entity/Q6971630"},
        "Starbucks": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Starbucks", "wikidata": "https://www.wikidata.org/entity/Q189658"},
    },
    "mens-grooming": {
        "safety razor": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Safety_razor"},
        "electric shaver": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Electric_shaver", "wikidata": "https://www.wikidata.org/entity/Q17457835"},
        "beard trimmer": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Hair_clipper"},
        "aftershave": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Aftershave", "wikidata": "https://www.wikidata.org/entity/Q1545022"},
        "pomade": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Pomade"},
        "sunscreen": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Sunscreen"},
        "ingrown hair": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Ingrown_hair"},
        "pseudofolliculitis barbae": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Pseudofolliculitis_barbae", "wikidata": "https://www.wikidata.org/entity/Q376092"},
        "razor burn": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Razor_burn"},
        "folliculitis": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Folliculitis", "wikidata": "https://www.wikidata.org/entity/Q942755"},
        "dermatitis": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Dermatitis"},
        "seborrheic dermatitis": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Seborrhoeic_dermatitis", "wikidata": "https://www.wikidata.org/entity/Q448310"},
        "acne vulgaris": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Acne", "wikidata": "https://www.wikidata.org/entity/Q79928"},
        "androgenetic alopecia": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Pattern_hair_loss", "wikidata": "https://www.wikidata.org/entity/Q2276095"},
        "minoxidil": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Minoxidil"},
        "finasteride": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Finasteride", "wikidata": "https://www.wikidata.org/entity/Q424167"},
        "salicylic acid": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Salicylic_acid", "wikidata": "https://www.wikidata.org/entity/Q193572"},
        "exfoliation": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Exfoliation_(cosmetology)"},
        "keratin": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Keratin"},
        "hair follicle": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Hair_follicle", "wikidata": "https://www.wikidata.org/entity/Q866324"},
        "Gillette": {"@type": "Brand", "sameAs": "https://en.wikipedia.org/wiki/Gillette", "wikidata": "https://www.wikidata.org/entity/Q503592"},
        "Philips Norelco": {"@type": "Brand", "sameAs": "https://en.wikipedia.org/wiki/Philips_Norelco", "wikidata": "https://www.wikidata.org/entity/Q3343650"},
        "Wahl Clipper": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Wahl_Clipper", "wikidata": "https://www.wikidata.org/entity/Q7959809"},
        "American Academy of Dermatology": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/American_Academy_of_Dermatology", "wikidata": "https://www.wikidata.org/entity/Q4742879"},
        "Food and Drug Administration": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Food_and_Drug_Administration", "wikidata": "https://www.wikidata.org/entity/Q204711"},
    },
    "oral-care": {
        "gingivitis": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Gingivitis", "wikidata": "https://www.wikidata.org/entity/Q673083"},
        "periodontitis": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Periodontitis", "wikidata": "https://www.wikidata.org/entity/Q520127"},
        "dental plaque": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Dental_plaque", "wikidata": "https://www.wikidata.org/entity/Q143504"},
        "tooth enamel": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Tooth_enamel", "wikidata": "https://www.wikidata.org/entity/Q143942"},
        "Streptococcus mutans": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Streptococcus_mutans", "wikidata": "https://www.wikidata.org/entity/Q131452"},
        "dental floss": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Dental_floss", "wikidata": "https://www.wikidata.org/entity/Q143978"},
        "electric toothbrush": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Electric_toothbrush", "wikidata": "https://www.wikidata.org/entity/Q979744"},
        "water flosser": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Oral_irrigator", "wikidata": "https://www.wikidata.org/entity/Q1457473"},
        "toothpaste": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Toothpaste", "wikidata": "https://www.wikidata.org/entity/Q35855"},
        "teeth whitening": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Tooth_whitening"},
        "sodium fluoride": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Sodium_fluoride", "wikidata": "https://www.wikidata.org/entity/Q407520"},
        "chlorhexidine": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Chlorhexidine", "wikidata": "https://www.wikidata.org/entity/Q15646788"},
        "hydrogen peroxide": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Hydrogen_peroxide", "wikidata": "https://www.wikidata.org/entity/Q171877"},
        "Oral-B": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Oral-B", "wikidata": "https://www.wikidata.org/entity/Q1987067"},
        "American Dental Association": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/American_Dental_Association", "wikidata": "https://www.wikidata.org/entity/Q4743596"},
        "Food and Drug Administration": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Food_and_Drug_Administration", "wikidata": "https://www.wikidata.org/entity/Q204711"},
    },
    "home-cleaning": {
        "HEPA filter": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/HEPA", "wikidata": "https://www.wikidata.org/entity/Q948441"},
        "robot vacuum": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Robotic_vacuum_cleaner", "wikidata": "https://www.wikidata.org/entity/Q168577"},
        "microfiber cloth": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Microfibre_cloth", "wikidata": "https://www.wikidata.org/entity/Q1933853"},
        "steam cleaner": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Steam_cleaning"},
        "detergent": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Detergent", "wikidata": "https://www.wikidata.org/entity/Q334637"},
        "baking soda": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Sodium_bicarbonate", "wikidata": "https://www.wikidata.org/entity/Q179731"},
        "white vinegar": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Distilled_vinegar", "wikidata": "https://www.wikidata.org/entity/Q898765"},
        "bleach": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Bleach"},
        "sodium hypochlorite": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Sodium_hypochlorite", "wikidata": "https://www.wikidata.org/entity/Q407204"},
        "surfactant": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Surfactant", "wikidata": "https://www.wikidata.org/entity/Q191154"},
        "allergen": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Allergen", "wikidata": "https://www.wikidata.org/entity/Q186752"},
        "mold": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Mold", "wikidata": "https://www.wikidata.org/entity/Q159341"},
        "dust": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Dust", "wikidata": "https://www.wikidata.org/entity/Q165632"},
        "house dust mites": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/House_dust_mite", "wikidata": "https://www.wikidata.org/entity/Q2822634"},
        "EPA": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/United_States_Environmental_Protection_Agency", "wikidata": "https://www.wikidata.org/entity/Q460173"},
        "iRobot": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/IRobot", "wikidata": "https://www.wikidata.org/entity/Q285161"},
        "NSF International": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/National_Sanitation_Foundation", "wikidata": "https://www.wikidata.org/entity/Q6955296"},
    },
    "healthy-cooking": {
        "air fryer": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Air_fryer"},
        "pressure cooker": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Pressure_cooker", "wikidata": "https://www.wikidata.org/entity/Q271997"},
        "Instant Pot": {"@type": "Brand", "sameAs": "https://en.wikipedia.org/wiki/Instant_Pot", "wikidata": "https://www.wikidata.org/entity/Q48989064"},
        "cast iron skillet": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Cast-iron_cookware", "wikidata": "https://www.wikidata.org/entity/Q3294507"},
        "cast-iron cookware": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Cast-iron_cookware", "wikidata": "https://www.wikidata.org/entity/Q3294507"},
        "wok": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Wok", "wikidata": "https://www.wikidata.org/entity/Q208364"},
        "food processor": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Food_processor"},
        "sous vide": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Sous_vide"},
        "meal prep": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Meal_preparation"},
        "non-stick coating": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Non-stick_surface"},
        "PTFE": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Polytetrafluoroethylene"},
        "BPA": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Bisphenol_A"},
        "olive oil": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Olive_oil"},
        "avocado oil": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Avocado_oil", "wikidata": "https://www.wikidata.org/entity/Q2918735"},
        "coconut oil": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Coconut_oil", "wikidata": "https://www.wikidata.org/entity/Q216235"},
        "trans fat": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Trans_fat", "wikidata": "https://www.wikidata.org/entity/Q243465"},
        "omega-3 fatty acid": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Omega-3_fatty_acid", "wikidata": "https://www.wikidata.org/entity/Q191756"},
        "dietary fiber": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Dietary_fiber", "wikidata": "https://www.wikidata.org/entity/Q215210"},
        "acrylamide": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Acrylamide", "wikidata": "https://www.wikidata.org/entity/Q342939"},
        "cardiovascular disease": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Cardiovascular_disease", "wikidata": "https://www.wikidata.org/entity/Q389735"},
        "type 2 diabetes": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Type_2_diabetes", "wikidata": "https://www.wikidata.org/entity/Q3025883"},
        "FDA": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Food_and_Drug_Administration", "wikidata": "https://www.wikidata.org/entity/Q204711"},
        "American Heart Association": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/American_Heart_Association", "wikidata": "https://www.wikidata.org/entity/Q464880"},
        "World Health Organization": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/World_Health_Organization", "wikidata": "https://www.wikidata.org/entity/Q7817"},
        "United States Department of Agriculture": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/United_States_Department_of_Agriculture", "wikidata": "https://www.wikidata.org/entity/Q501542"},
    },
    "home-office": {
        "ergonomic chair": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Office_chair", "wikidata": "https://www.wikidata.org/entity/Q125507956"},
        "standing desk": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Standing_desk", "wikidata": "https://www.wikidata.org/entity/Q3416733"},
        "monitor arm": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Monitor_mount", "wikidata": "https://www.wikidata.org/entity/Q25325298"},
        "anti-fatigue mat": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Anti-fatigue_mat", "wikidata": "https://www.wikidata.org/entity/Q117208343"},
        "noise-canceling headphones": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Noise-cancelling_headphones", "wikidata": "https://www.wikidata.org/entity/Q653752"},
        "webcam": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Webcam", "wikidata": "https://www.wikidata.org/entity/Q29576"},
        "desk lamp": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Desk_lamp", "wikidata": "https://www.wikidata.org/entity/Q3216816"},
        "lumbar support": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Lumbar_support", "wikidata": "https://www.wikidata.org/entity/Q1579771"},
        "blue light filter": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Blue_light_filter"},
        "blue light": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/High-energy_visible_light", "wikidata": "https://www.wikidata.org/entity/Q1573329"},
        "productivity": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Productivity"},
        "carpal tunnel syndrome": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Carpal_tunnel_syndrome", "wikidata": "https://www.wikidata.org/entity/Q332293"},
        "RSI": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Repetitive_strain_injury", "wikidata": "https://www.wikidata.org/entity/Q877796"},
        "musculoskeletal disorder": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Musculoskeletal_disorder", "wikidata": "https://www.wikidata.org/entity/Q4116663"},
        "eye strain": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Eye_strain", "wikidata": "https://www.wikidata.org/entity/Q749159"},
        "OSHA": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Occupational_Safety_and_Health_Administration", "wikidata": "https://www.wikidata.org/entity/Q746186"},
        "NIOSH": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/National_Institute_for_Occupational_Safety_and_Health", "wikidata": "https://www.wikidata.org/entity/Q60346"},
    },
    "water-air-quality": {
        "HEPA filter": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/HEPA", "wikidata": "https://www.wikidata.org/entity/Q948441"},
        "air purifier": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Air_purifier", "wikidata": "https://www.wikidata.org/entity/Q132250"},
        "water filter": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Water_filter", "wikidata": "https://www.wikidata.org/entity/Q7973543"},
        "water softener": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Water_softening", "wikidata": "https://www.wikidata.org/entity/Q1432864"},
        "dehumidifier": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Dehumidifier", "wikidata": "https://www.wikidata.org/entity/Q1231567"},
        "reverse osmosis": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Reverse_osmosis", "wikidata": "https://www.wikidata.org/entity/Q49670"},
        "activated carbon": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Activated_carbon", "wikidata": "https://www.wikidata.org/entity/Q190878"},
        "TDS": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Total_dissolved_solids", "wikidata": "https://www.wikidata.org/entity/Q1432865"},
        "VOC": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Volatile_organic_compound", "wikidata": "https://www.wikidata.org/entity/Q910267"},
        "PFAS": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Per-_and_polyfluoroalkyl_substances", "wikidata": "https://www.wikidata.org/entity/Q648037"},
        "particulate matter": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Particulates", "wikidata": "https://www.wikidata.org/entity/Q1047440"},
        "radon": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Radon", "wikidata": "https://www.wikidata.org/entity/Q1134"},
        "lead contamination": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Lead_poisoning", "wikidata": "https://www.wikidata.org/entity/Q230478"},
        "carbon monoxide": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Carbon_monoxide", "wikidata": "https://www.wikidata.org/entity/Q2025"},
        "mold": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Mold", "wikidata": "https://www.wikidata.org/entity/Q159341"},
        "indoor air quality": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Indoor_air_quality", "wikidata": "https://www.wikidata.org/entity/Q1315033"},
        "EPA": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/United_States_Environmental_Protection_Agency", "wikidata": "https://www.wikidata.org/entity/Q460173"},
        "WHO": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/World_Health_Organization", "wikidata": "https://www.wikidata.org/entity/Q7817"},
        "NSF International": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/NSF_International", "wikidata": "https://www.wikidata.org/entity/Q6951880"},
    },
    "korean-skincare": {
        "K-beauty": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/K-beauty", "wikidata": "https://www.wikidata.org/entity/Q28455696"},
        "hyaluronic acid": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Hyaluronic_acid", "wikidata": "https://www.wikidata.org/entity/Q337231"},
        "retinol": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Retinol", "wikidata": "https://www.wikidata.org/entity/Q424976"},
        "niacinamide": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Nicotinamide", "wikidata": "https://www.wikidata.org/entity/Q192423"},
        "ceramide": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Ceramide", "wikidata": "https://www.wikidata.org/entity/Q424213"},
        "alpha hydroxy acid": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Alpha_hydroxy_acid", "wikidata": "https://www.wikidata.org/entity/Q413302"},
        "beta hydroxy acid": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Beta_hydroxy_acid", "wikidata": "https://www.wikidata.org/entity/Q4897299"},
        "panthenol": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Panthenol", "wikidata": "https://www.wikidata.org/entity/Q196473"},
        "glycerol": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Glycerol", "wikidata": "https://www.wikidata.org/entity/Q132501"},
        "ascorbic acid": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Ascorbic_acid", "wikidata": "https://www.wikidata.org/entity/Q193598"},
        "collagen": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Collagen", "wikidata": "https://www.wikidata.org/entity/Q26868"},
        "melanin": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Melanin", "wikidata": "https://www.wikidata.org/entity/Q187526"},
        "Centella asiatica": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Centella_asiatica", "wikidata": "https://www.wikidata.org/entity/Q324714"},
        "snail mucin": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Snail_slime", "wikidata": "https://www.wikidata.org/entity/Q7546938"},
        "sunscreen": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Sunscreen", "wikidata": "https://www.wikidata.org/entity/Q827658"},
        "double cleansing": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Oil_cleansing_method"},
        "hyperpigmentation": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Hyperpigmentation", "wikidata": "https://www.wikidata.org/entity/Q1641068"},
        "atopic dermatitis": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Atopic_dermatitis", "wikidata": "https://www.wikidata.org/entity/Q199678"},
        "transepidermal water loss": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Transepidermal_water_loss", "wikidata": "https://www.wikidata.org/entity/Q7833972"},
        "Amorepacific Corporation": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Amorepacific_Corporation", "wikidata": "https://www.wikidata.org/entity/Q490142"},
        "LG H&H": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/LG_H%26H", "wikidata": "https://www.wikidata.org/entity/Q16169971"},
        "Laneige": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Laneige", "wikidata": "https://www.wikidata.org/entity/Q16935511"},
        "Ministry of Food and Drug Safety": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Ministry_of_Food_and_Drug_Safety", "wikidata": "https://www.wikidata.org/entity/Q482905"},
    },
    "makeup-beauty": {
        "foundation": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Foundation_(cosmetics)", "wikidata": "https://www.wikidata.org/entity/Q1418455"},
        "concealer": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Concealer"},
        "mascara": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Mascara", "wikidata": "https://www.wikidata.org/entity/Q324120"},
        "primer": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Primer_(cosmetics)"},
        "lipstick": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Lipstick", "wikidata": "https://www.wikidata.org/entity/Q184191"},
        "blush": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Rouge_(cosmetics)", "wikidata": "https://www.wikidata.org/entity/Q181791"},
        "eyeshadow": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Eye_shadow", "wikidata": "https://www.wikidata.org/entity/Q964307"},
        "contouring": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Contouring"},
        "setting spray": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Setting_spray"},
        "hyaluronic acid": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Hyaluronic_acid", "wikidata": "https://www.wikidata.org/entity/Q337231"},
        "retinol": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Retinol", "wikidata": "https://www.wikidata.org/entity/Q424976"},
        "niacinamide": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Nicotinamide", "wikidata": "https://www.wikidata.org/entity/Q192423"},
        "ceramide": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Ceramide", "wikidata": "https://www.wikidata.org/entity/Q424213"},
        "titanium dioxide": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Titanium_dioxide", "wikidata": "https://www.wikidata.org/entity/Q193521"},
        "talc": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Talc", "wikidata": "https://www.wikidata.org/entity/Q134583"},
        "paraben": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Paraben"},
        "cruelty-free cosmetics": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Cruelty-free_cosmetics"},
        "L'Oréal": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/L%27Or%C3%A9al", "wikidata": "https://www.wikidata.org/entity/Q156077"},
        "Maybelline": {"@type": "Brand", "sameAs": "https://en.wikipedia.org/wiki/Maybelline", "wikidata": "https://www.wikidata.org/entity/Q1351054"},
        "Estée Lauder Companies": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Est%C3%A9e_Lauder_Companies", "wikidata": "https://www.wikidata.org/entity/Q1260606"},
        "FDA": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Food_and_Drug_Administration", "wikidata": "https://www.wikidata.org/entity/Q204711"},
    },
    "korean-medical-tourism": {
        "medical tourism": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Medical_tourism", "wikidata": "https://www.wikidata.org/entity/Q757232"},
        "rhinoplasty": {"@type": "MedicalProcedure", "sameAs": "https://en.wikipedia.org/wiki/Rhinoplasty", "wikidata": "https://www.wikidata.org/entity/Q840929"},
        "blepharoplasty": {"@type": "MedicalProcedure", "sameAs": "https://en.wikipedia.org/wiki/Blepharoplasty", "wikidata": "https://www.wikidata.org/entity/Q2559992"},
        "double eyelid surgery": {"@type": "MedicalProcedure", "sameAs": "https://en.wikipedia.org/wiki/East_Asian_blepharoplasty", "wikidata": "https://www.wikidata.org/entity/Q5327743"},
        "dental implant": {"@type": "MedicalProcedure", "sameAs": "https://en.wikipedia.org/wiki/Dental_implant", "wikidata": "https://www.wikidata.org/entity/Q143680"},
        "LASIK": {"@type": "MedicalProcedure", "sameAs": "https://en.wikipedia.org/wiki/LASIK", "wikidata": "https://www.wikidata.org/entity/Q278846"},
        "SMILE": {"@type": "MedicalProcedure", "sameAs": "https://en.wikipedia.org/wiki/Small_incision_lenticule_extraction", "wikidata": "https://www.wikidata.org/entity/Q1404556"},
        "PRK": {"@type": "MedicalProcedure", "sameAs": "https://en.wikipedia.org/wiki/Photorefractive_keratectomy", "wikidata": "https://www.wikidata.org/entity/Q565832"},
        "liposuction": {"@type": "MedicalProcedure", "sameAs": "https://en.wikipedia.org/wiki/Liposuction", "wikidata": "https://www.wikidata.org/entity/Q825490"},
        "hair transplant": {"@type": "MedicalProcedure", "sameAs": "https://en.wikipedia.org/wiki/Hair_transplantation", "wikidata": "https://www.wikidata.org/entity/Q685286"},
        "health screening": {"@type": "MedicalProcedure", "sameAs": "https://en.wikipedia.org/wiki/Screening_(medicine)", "wikidata": "https://www.wikidata.org/entity/Q1163564"},
        "Botox": {"@type": "Brand", "sameAs": "https://en.wikipedia.org/wiki/Botulinum_toxin", "wikidata": "https://www.wikidata.org/entity/Q208413"},
        "myopia": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Myopia", "wikidata": "https://www.wikidata.org/entity/Q168403"},
        "ptosis": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Ptosis_(eyelid)", "wikidata": "https://www.wikidata.org/entity/Q622427"},
        "alopecia": {"@type": "MedicalCondition", "sameAs": "https://en.wikipedia.org/wiki/Hair_loss", "wikidata": "https://www.wikidata.org/entity/Q181391"},
        "JCI": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Joint_Commission_International", "wikidata": "https://www.wikidata.org/entity/Q1703687"},
        "MFDS": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Ministry_of_Food_and_Drug_Safety", "wikidata": "https://www.wikidata.org/entity/Q482905"},
        "HIRA": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Health_Insurance_Review_and_Assessment_Service", "wikidata": "https://www.wikidata.org/entity/Q16179935"},
        "Seoul": {"@type": "Place", "sameAs": "https://en.wikipedia.org/wiki/Seoul", "wikidata": "https://www.wikidata.org/entity/Q8684"},
        "South Korea": {"@type": "Place", "sameAs": "https://en.wikipedia.org/wiki/South_Korea", "wikidata": "https://www.wikidata.org/entity/Q884"},
        "Gangnam": {"@type": "Place", "sameAs": "https://en.wikipedia.org/wiki/Gangnam_District", "wikidata": "https://www.wikidata.org/entity/Q20398"},
        "Apgujeong": {"@type": "Place", "sameAs": "https://en.wikipedia.org/wiki/Apgujeong-dong", "wikidata": "https://www.wikidata.org/entity/Q490602"},
        "Samsung Medical Center": {"@type": "Hospital", "sameAs": "https://en.wikipedia.org/wiki/Samsung_Medical_Center", "wikidata": "https://www.wikidata.org/entity/Q624119"},
        "Asan Medical Center": {"@type": "Hospital", "sameAs": "https://en.wikipedia.org/wiki/Asan_Medical_Center", "wikidata": "https://www.wikidata.org/entity/Q4803501"},
        "Severance Hospital": {"@type": "Hospital", "sameAs": "https://en.wikipedia.org/wiki/Severance_Hospital", "wikidata": "https://www.wikidata.org/entity/Q625321"},
        "Seoul National University Hospital": {"@type": "Hospital", "sameAs": "https://en.wikipedia.org/wiki/Seoul_National_University_Hospital", "wikidata": "https://www.wikidata.org/entity/Q4403855"},
    },
    "korean-used-cars": {
        "used car": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Used_car", "wikidata": "https://www.wikidata.org/entity/Q1137287"},
        "Hyundai Motor Company": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Hyundai_Motor_Company", "wikidata": "https://www.wikidata.org/entity/Q55931"},
        "Kia": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Kia", "wikidata": "https://www.wikidata.org/entity/Q35349"},
        "Genesis Motor": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Genesis_Motor", "wikidata": "https://www.wikidata.org/entity/Q21451523"},
        "KG Mobility": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/KG_Mobility", "wikidata": "https://www.wikidata.org/entity/Q221869"},
        "Hyundai Motor Group": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Hyundai_Motor_Group", "wikidata": "https://www.wikidata.org/entity/Q59243"},
        "MOLIT": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Ministry_of_Land,_Infrastructure_and_Transport", "wikidata": "https://www.wikidata.org/entity/Q9398575"},
        "KFTC": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Fair_Trade_Commission_(South_Korea)", "wikidata": "https://www.wikidata.org/entity/Q624479"},
        "Hyundai Sonata": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Hyundai_Sonata", "wikidata": "https://www.wikidata.org/entity/Q482458"},
        "Hyundai Tucson": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Hyundai_Tucson", "wikidata": "https://www.wikidata.org/entity/Q482430"},
        "Hyundai Elantra": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Hyundai_Elantra", "wikidata": "https://www.wikidata.org/entity/Q482530"},
        "Kia Sorento": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Kia_Sorento", "wikidata": "https://www.wikidata.org/entity/Q489836"},
        "Kia Sportage": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Kia_Sportage", "wikidata": "https://www.wikidata.org/entity/Q145527"},
        "Kia K5": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Kia_K5", "wikidata": "https://www.wikidata.org/entity/Q12586722"},
        "Kia Forte": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Kia_Forte", "wikidata": "https://www.wikidata.org/entity/Q489621"},
        "Kia Rio": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Kia_Rio", "wikidata": "https://www.wikidata.org/entity/Q493781"},
        "electric vehicle": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Electric_vehicle", "wikidata": "https://www.wikidata.org/entity/Q13629441"},
        "hybrid electric vehicle": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Hybrid_electric_vehicle", "wikidata": "https://www.wikidata.org/entity/Q11083590"},
        "sport utility vehicle": {"@type": "Product", "sameAs": "https://en.wikipedia.org/wiki/Sport_utility_vehicle", "wikidata": "https://www.wikidata.org/entity/Q192152"},
        "internal combustion engine": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Internal_combustion_engine", "wikidata": "https://www.wikidata.org/entity/Q12757"},
        "diesel engine": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Diesel_engine", "wikidata": "https://www.wikidata.org/entity/Q174174"},
        "automatic transmission": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Automatic_transmission", "wikidata": "https://www.wikidata.org/entity/Q843592"},
        "VIN": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Vehicle_identification_number", "wikidata": "https://www.wikidata.org/entity/Q304948"},
        "odometer": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Odometer", "wikidata": "https://www.wikidata.org/entity/Q745105"},
        "OBD-II": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/On-board_diagnostics", "wikidata": "https://www.wikidata.org/entity/Q57573"},
        "vehicle inspection": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Vehicle_inspection", "wikidata": "https://www.wikidata.org/entity/Q978659"},
        "customs clearance": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Customs", "wikidata": "https://www.wikidata.org/entity/Q182290"},
        "Ro-Ro shipping": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Roll-on/roll-off", "wikidata": "https://www.wikidata.org/entity/Q473932"},
        "depreciation": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Depreciation", "wikidata": "https://www.wikidata.org/entity/Q114403"},
        "automotive industry in South Korea": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Automotive_industry_in_South_Korea", "wikidata": "https://www.wikidata.org/entity/Q4826746"},
        "Incheon": {"@type": "Place", "sameAs": "https://en.wikipedia.org/wiki/Incheon", "wikidata": "https://www.wikidata.org/entity/Q20934"},
        "spare part": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Spare_part", "wikidata": "https://www.wikidata.org/entity/Q1364774"},
        "OEM": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Original_equipment_manufacturer", "wikidata": "https://www.wikidata.org/entity/Q267558"},
        "aftermarket": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Automotive_aftermarket", "wikidata": "https://www.wikidata.org/entity/Q376134"},
        "engine": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Engine", "wikidata": "https://www.wikidata.org/entity/Q44167"},
        "transmission": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Transmission_(mechanics)", "wikidata": "https://www.wikidata.org/entity/Q16259746"},
        "brake": {"@type": "Thing", "sameAs": "https://en.wikipedia.org/wiki/Brake", "wikidata": "https://www.wikidata.org/entity/Q1534839"},
        "Hyundai Mobis": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Hyundai_Mobis", "wikidata": "https://www.wikidata.org/entity/Q497534"},
        "Hankook Tire": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Hankook_Tire_%26_Technology", "wikidata": "https://www.wikidata.org/entity/Q493094"},
        "HL Mando": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/HL_Mando", "wikidata": "https://www.wikidata.org/entity/Q6748120"},
        "KAMA": {"@type": "Organization", "sameAs": "https://en.wikipedia.org/wiki/Korea_Automobile_Manufacturers_Association", "wikidata": "https://www.wikidata.org/entity/Q626230"},
    },
}


# ---------------------------------------------------------------------------
# Entity relationships — subject-verb-object triples per niche
# Used by article_template.py for semantic connection guidance in LLM prompts
# ---------------------------------------------------------------------------

ENTITY_RELATIONSHIPS = {
    "dog-comfort": [
        ("arthritis", "causes", "joint pain"),
        ("orthopedic bed", "relieves", "arthritis"),
        ("memory foam", "component of", "orthopedic bed"),
        ("separation anxiety", "treated by", "crate training"),
        ("hip dysplasia", "common in", "german shepherd"),
        ("hip dysplasia", "common in", "golden retriever"),
        ("hip dysplasia", "common in", "labrador retriever"),
        ("enzyme cleaner", "removes", "pet odor"),
        ("crate training", "reduces", "separation anxiety"),
        ("orthopedic bed", "supports", "hip dysplasia"),
    ],
    "camping-gear": [
        ("Gore-Tex", "component of", "tent"),
        ("down feather", "component of", "sleeping bag"),
        ("sleeping bag", "prevents", "hypothermia"),
        ("sleeping bag", "prevents", "frostbite"),
        ("camping stove", "required for", "backpacking"),
        ("Leave No Trace", "regulates", "backpacking"),
        ("National Park Service", "certifies", "Leave No Trace"),
        ("water purification", "essential for", "ultralight backpacking"),
        ("ASTM International", "certifies", "sleeping bag"),
        ("Mountain Safety Research", "manufactures", "camping stove"),
    ],
    "cat-care": [
        ("taurine", "essential for", "cat health"),
        ("hairball", "prevented by", "regular grooming"),
        ("cat scratching post", "prevents", "furniture damage"),
        ("catnip", "stimulates", "cat behavior"),
        ("toxoplasmosis", "transmitted by", "cat litter"),
        ("feline lower urinary tract disease", "common in", "indoor cats"),
        ("bentonite", "component of", "cat litter"),
        ("AAFCO", "regulates", "taurine"),
        ("catnip", "encourages use of", "cat scratching post"),
        ("Maine Coon", "predisposed to", "chronic kidney disease"),
    ],
    "home-coffee": [
        ("Arabica coffee", "preferred over", "Robusta coffee"),
        ("coffee grinder", "required for", "pour-over coffee"),
        ("descaling", "maintains", "espresso machine"),
        ("caffeine", "extracted from", "Arabica coffee"),
        ("Specialty Coffee Association", "certifies", "coffee quality"),
        ("cold brew", "requires", "coarse grind"),
        ("paper coffee filter", "used in", "pour-over coffee"),
        ("Moka pot", "alternative to", "espresso machine"),
        ("chlorogenic acid", "found in", "Arabica coffee"),
        ("chlorogenic acid", "contributes to", "gastroesophageal reflux disease"),
        ("caffeine", "causes", "insomnia"),
        ("International Coffee Organization", "regulates", "Arabica coffee"),
        ("Food and Drug Administration", "regulates", "caffeine"),
    ],
    "mens-grooming": [
        ("safety razor", "prevents", "ingrown hair"),
        ("exfoliation", "prevents", "razor burn"),
        ("minoxidil", "treats", "androgenetic alopecia"),
        ("finasteride", "treats", "androgenetic alopecia"),
        ("keratin", "strengthened by", "proper care"),
        ("sunscreen", "prevents", "dermatitis"),
        ("pseudofolliculitis barbae", "causes", "folliculitis"),
        ("electric shaver", "prevents", "pseudofolliculitis barbae"),
        ("salicylic acid", "treats", "acne vulgaris"),
        ("salicylic acid", "treats", "seborrheic dermatitis"),
        ("Food and Drug Administration", "regulates", "finasteride"),
        ("Philips Norelco", "manufactures", "electric shaver"),
        ("Gillette", "manufactures", "aftershave"),
        ("Wahl Clipper", "manufactures", "beard trimmer"),
        ("folliculitis", "affects", "hair follicle"),
        ("American Academy of Dermatology", "publishes guidelines on", "acne vulgaris"),
    ],
    "oral-care": [
        ("dental plaque", "causes", "gingivitis"),
        ("gingivitis", "progresses to", "periodontitis"),
        ("Streptococcus mutans", "component of", "dental plaque"),
        ("dental floss", "removes", "dental plaque"),
        ("electric toothbrush", "removes", "dental plaque"),
        ("water flosser", "removes", "dental plaque"),
        ("toothpaste", "contains", "sodium fluoride"),
        ("sodium fluoride", "strengthens", "tooth enamel"),
        ("chlorhexidine", "reduces", "dental plaque"),
        ("American Dental Association", "certifies", "toothpaste"),
        ("dental floss", "prevents", "gingivitis"),
        ("American Dental Association", "certifies", "oral care products"),
        ("water flosser", "alternative to", "dental floss"),
    ],
    "home-cleaning": [
        ("HEPA filter", "removes", "allergen"),
        ("HEPA filter", "removes", "dust"),
        ("microfiber cloth", "traps", "dust"),
        ("robot vacuum", "uses", "HEPA filter"),
        ("baking soda", "neutralizes", "odor"),
        ("baking soda", "reacts with", "white vinegar"),
        ("bleach", "kills", "mold"),
        ("sodium hypochlorite", "kills", "mold"),
        ("detergent", "contains", "surfactant"),
        ("house dust mites", "produce", "allergen"),
        ("dust", "contains", "house dust mites"),
        ("EPA", "regulates", "sodium hypochlorite"),
        ("EPA", "regulates", "cleaning chemicals"),
    ],
    "healthy-cooking": [
        ("air fryer", "reduces", "oil usage"),
        ("olive oil", "healthier than", "vegetable oil"),
        ("PTFE", "used in", "non-stick coating"),
        ("BPA", "found in", "plastic containers"),
        ("FDA", "regulates", "food safety"),
        ("sous vide", "maintains", "precise temperature"),
        ("trans fat", "causes", "cardiovascular disease"),
        ("trans fat", "increases risk of", "type 2 diabetes"),
        ("omega-3 fatty acid", "prevents", "cardiovascular disease"),
        ("dietary fiber", "prevents", "type 2 diabetes"),
        ("American Heart Association", "recommends", "avocado oil"),
        ("American Heart Association", "advises against", "coconut oil"),
        ("World Health Organization", "targets elimination of", "trans fat"),
        ("World Health Organization", "classifies", "acrylamide"),
        ("United States Department of Agriculture", "publishes guidelines on", "dietary fiber"),
        ("Instant Pot", "subclass of", "pressure cooker"),
    ],
    "home-office": [
        ("ergonomic chair", "prevents", "carpal tunnel syndrome"),
        ("ergonomic chair", "prevents", "RSI"),
        ("lumbar support", "component of", "ergonomic chair"),
        ("standing desk", "reduces", "back pain"),
        ("standing desk", "prevents", "musculoskeletal disorder"),
        ("anti-fatigue mat", "required for", "standing desk"),
        ("blue light filter", "reduces", "eye strain"),
        ("blue light", "causes", "eye strain"),
        ("monitor arm", "reduces", "eye strain"),
        ("carpal tunnel syndrome", "form of", "RSI"),
        ("RSI", "caused by", "poor ergonomics"),
        ("OSHA", "sets standards for", "workplace safety"),
        ("OSHA", "regulates", "musculoskeletal disorder"),
        ("NIOSH", "researches", "RSI"),
    ],
    "water-air-quality": [
        ("reverse osmosis", "removes", "TDS"),
        ("reverse osmosis", "removes", "lead contamination"),
        ("reverse osmosis", "removes", "PFAS"),
        ("activated carbon", "removes", "VOC"),
        ("HEPA filter", "captures", "particulate matter"),
        ("air purifier", "reduces", "particulate matter"),
        ("air purifier", "uses", "HEPA filter"),
        ("dehumidifier", "reduces", "mold"),
        ("mold", "affects", "indoor air quality"),
        ("water filter", "removes", "chlorine"),
        ("water softener", "removes", "hard water minerals"),
        ("EPA", "sets limits for", "lead contamination"),
        ("EPA", "recommends action levels for", "radon"),
        ("WHO", "provides guidelines on", "indoor air quality"),
        ("NSF International", "certifies", "water filter"),
        ("carbon monoxide", "detected by", "carbon monoxide detector"),
        ("radon", "detected by", "radon detector"),
    ],
    "korean-skincare": [
        ("hyaluronic acid", "hydrates", "skin"),
        ("retinol", "stimulates", "collagen"),
        ("niacinamide", "reduces", "hyperpigmentation"),
        ("niacinamide", "inhibits", "melanin"),
        ("melanin", "causes", "hyperpigmentation"),
        ("double cleansing", "foundation of", "K-beauty"),
        ("ceramide", "repairs", "skin barrier"),
        ("ceramide", "prevents", "transepidermal water loss"),
        ("alpha hydroxy acid", "exfoliates", "dead skin cells"),
        ("beta hydroxy acid", "unclogs", "pores"),
        ("Centella asiatica", "soothes", "atopic dermatitis"),
        ("panthenol", "hydrates", "skin"),
        ("glycerol", "hydrates", "skin"),
        ("ascorbic acid", "prevents", "hyperpigmentation"),
        ("snail mucin", "hydrates", "skin"),
        ("sunscreen", "prevents", "UV damage"),
        ("Ministry of Food and Drug Safety", "regulates", "K-beauty"),
        ("Amorepacific Corporation", "manufactures", "Laneige"),
        ("LG H&H", "competes with", "Amorepacific Corporation"),
    ],
    "makeup-beauty": [
        ("primer", "applied before", "foundation"),
        ("concealer", "covers", "dark circles"),
        ("setting spray", "locks in", "makeup"),
        ("talc", "ingredient in", "eyeshadow"),
        ("titanium dioxide", "ingredient in", "foundation"),
        ("titanium dioxide", "provides", "UV protection"),
        ("paraben", "preservative in", "mascara"),
        ("hyaluronic acid", "ingredient in", "lipstick"),
        ("niacinamide", "brightens", "skin tone"),
        ("retinol", "targets", "fine lines"),
        ("ceramide", "strengthens", "skin barrier"),
        ("contouring", "technique used with", "blush"),
        ("FDA", "regulates", "cosmetic safety"),
        ("L'Oréal", "owns", "Maybelline"),
        ("Estée Lauder Companies", "competes with", "L'Oréal"),
        ("cruelty-free cosmetics", "certification applies to", "Maybelline"),
    ],
    "korean-medical-tourism": [
        ("rhinoplasty", "performed in", "Gangnam"),
        ("JCI", "accredits", "hospital quality"),
        ("JCI", "accredits", "Samsung Medical Center"),
        ("JCI", "accredits", "Severance Hospital"),
        ("blepharoplasty", "common procedure in", "Seoul"),
        ("blepharoplasty", "corrects", "ptosis"),
        ("double eyelid surgery", "performed in", "Apgujeong"),
        ("dental implant", "cheaper in", "South Korea"),
        ("MFDS", "regulates", "medical procedures"),
        ("MFDS", "regulates", "Botox"),
        ("Botox", "popular treatment in", "Gangnam"),
        ("health screening", "available at", "Samsung Medical Center"),
        ("SMILE", "treats", "myopia"),
        ("PRK", "treats", "myopia"),
        ("LASIK", "treats", "myopia"),
        ("hair transplant", "treats", "alopecia"),
        ("liposuction", "performed in", "Gangnam"),
        ("Apgujeong", "located in", "Gangnam"),
        ("Samsung Medical Center", "located in", "Seoul"),
        ("Asan Medical Center", "located in", "Seoul"),
        ("Severance Hospital", "located in", "Seoul"),
        ("Seoul National University Hospital", "located in", "Seoul"),
        ("HIRA", "evaluates", "hospital quality"),
    ],
    "korean-used-cars": [
        ("Hyundai Motor Group", "owns", "Hyundai Motor Company"),
        ("Hyundai Motor Company", "part of", "Hyundai Motor Group"),
        ("Kia", "partially owned by", "Hyundai Motor Company"),
        ("Genesis Motor", "owned by", "Hyundai Motor Company"),
        ("Hyundai Motor Company", "manufactures", "Hyundai Sonata"),
        ("Hyundai Motor Company", "manufactures", "Hyundai Tucson"),
        ("Hyundai Motor Company", "manufactures", "Hyundai Elantra"),
        ("Hyundai Motor Company", "manufactures", "electric vehicle"),
        ("Kia", "manufactures", "Kia Sorento"),
        ("Kia", "manufactures", "Kia Sportage"),
        ("Kia", "manufactures", "Kia K5"),
        ("Kia", "manufactures", "Kia Forte"),
        ("Kia", "manufactures", "Kia Rio"),
        ("Kia", "manufactures", "sport utility vehicle"),
        ("KG Mobility", "manufactures", "sport utility vehicle"),
        ("automotive industry in South Korea", "includes", "Hyundai Motor Company"),
        ("automotive industry in South Korea", "includes", "Kia"),
        ("automotive industry in South Korea", "includes", "KG Mobility"),
        ("MOLIT", "regulates", "automotive industry in South Korea"),
        ("MOLIT", "requires", "vehicle inspection"),
        ("KFTC", "regulates", "automotive industry in South Korea"),
        ("used car", "regulated by", "MOLIT"),
        ("used car", "identified by", "VIN"),
        ("used car", "measured by", "odometer"),
        ("used car", "may use", "automatic transmission"),
        ("used car", "may use", "diesel engine"),
        ("used car", "shipped via", "Ro-Ro shipping"),
        ("used car", "requires", "customs clearance"),
        ("used car", "exported from", "Incheon"),
        ("OBD-II", "used in", "vehicle inspection"),
        ("hybrid electric vehicle", "combines", "internal combustion engine"),
        ("depreciation", "affects", "used car"),
        ("Hyundai Mobis", "part of", "Hyundai Motor Group"),
        ("Hyundai Mobis", "manufactures", "spare part"),
        ("HL Mando", "manufactures", "brake"),
        ("Hankook Tire", "manufactures", "spare part"),
        ("engine", "component of", "used car"),
        ("transmission", "component of", "used car"),
        ("brake", "component of", "used car"),
        ("OEM", "applies to", "spare part"),
        ("aftermarket", "alternative to", "OEM"),
        ("KAMA", "represents", "Hyundai Motor Company"),
        ("KAMA", "represents", "Kia"),
        ("KAMA", "represents", "KG Mobility"),
    ],
}


# ---------------------------------------------------------------------------
# Fuzzy entity matching — handles plurals, hyphens, case variants
# ---------------------------------------------------------------------------

def _entity_variants(name: str) -> list[str]:
    """Generate matching variants for an entity name."""
    lower = name.lower()
    variants = {lower}
    # Hyphenated: "memory foam" -> "memory-foam"
    if " " in lower:
        variants.add(lower.replace(" ", "-"))
    # De-hyphenated: "non-stick" -> "non stick"
    if "-" in lower:
        variants.add(lower.replace("-", " "))
    # Simple plural: "bed" -> "beds", "filter" -> "filters"
    if not lower.endswith("s"):
        variants.add(lower + "s")
    # Possessive: "dog" also matches "dog's"
    variants.add(lower + "'s")
    return list(variants)


def scan_entity_coverage(niche_slug: str, html_content: str) -> dict:
    """
    Scan article HTML for entity mentions with frequency and position data.

    Returns:
        {
            "found": [{"name": str, "count": int, "first_pos": int, "in_heading": bool}, ...],
            "missing": [str, ...],
            "coverage_pct": float,
            "total_mentions": int,
            "density_per_1k": float,
        }
    """
    entities = NICHE_ENTITIES.get(niche_slug, {})
    if not entities:
        return {"found": [], "missing": [], "coverage_pct": 0, "total_mentions": 0, "density_per_1k": 0}

    content_lower = html_content.lower()
    # Extract heading text for heading-placement check
    heading_text = " ".join(re.findall(r"<h[23][^>]*>(.*?)</h[23]>", html_content, re.I)).lower()
    word_count = len(content_lower.split())

    found = []
    missing = []
    total_mentions = 0

    for name in entities:
        variants = _entity_variants(name)
        count = 0
        first_pos = len(content_lower)  # default: end
        for v in variants:
            c = content_lower.count(v)
            count += c
            if c > 0:
                pos = content_lower.find(v)
                first_pos = min(first_pos, pos)

        if count > 0:
            in_heading = any(v in heading_text for v in variants)
            found.append({
                "name": name,
                "count": count,
                "first_pos": first_pos,
                "in_heading": in_heading,
            })
            total_mentions += count
        else:
            missing.append(name)

    coverage_pct = len(found) / len(entities) * 100 if entities else 0
    density = (total_mentions / word_count * 1000) if word_count > 0 else 0

    # Sort found by salience proxy: frequency * position weight (earlier = higher)
    for f in found:
        # Position weight: entities in first 20% of content score 2x
        pos_weight = 2.0 if f["first_pos"] < len(content_lower) * 0.2 else 1.0
        heading_weight = 1.5 if f["in_heading"] else 1.0
        f["salience"] = round(f["count"] * pos_weight * heading_weight, 1)
    found.sort(key=lambda x: -x["salience"])

    return {
        "found": found,
        "missing": missing,
        "coverage_pct": round(coverage_pct, 1),
        "total_mentions": total_mentions,
        "density_per_1k": round(density, 1),
    }


def get_entities_for_article(niche_slug: str, html_content: str) -> dict:
    """
    Find which niche entities appear in article content.
    Returns: {"about": [top 3 by salience], "mentions": [remaining]}

    Improved: uses fuzzy matching + salience-based ranking (not discovery order).
    """
    coverage = scan_entity_coverage(niche_slug, html_content)
    entities = NICHE_ENTITIES.get(niche_slug, {})

    about = []
    mentions = []
    for i, f in enumerate(coverage["found"]):
        meta = entities.get(f["name"], {})
        entry = {"name": f["name"], "@type": meta.get("@type", "Thing"), "sameAs": meta.get("sameAs", "")}
        if meta.get("wikidata"):
            entry["wikidata"] = meta["wikidata"]
        if i < 3:
            about.append(entry)
        else:
            mentions.append(entry)

    return {"about": about, "mentions": mentions}


def get_entity_targets(niche_slug: str, keyword: str = "") -> dict:
    """
    Given a keyword, return which entities are most relevant for this article.

    Returns:
        {
            "primary": [{"name": str, "type": str, "reason": str}, ...],  # 3-5, MUST use
            "secondary": [{"name": str, "type": str}, ...],  # 3-5, should use
            "relationships": [("subj", "verb", "obj"), ...],  # relevant triples
        }
    """
    entities = NICHE_ENTITIES.get(niche_slug, {})
    relationships = ENTITY_RELATIONSHIPS.get(niche_slug, [])
    if not entities:
        return {"primary": [], "secondary": [], "relationships": []}

    kw_lower = keyword.lower() if keyword else ""

    # Score each entity by keyword relevance
    scored = []
    for name, meta in entities.items():
        score = 0
        reason = ""
        name_lower = name.lower()

        # Direct mention in keyword: highest relevance
        if name_lower in kw_lower:
            score += 10
            reason = "in keyword"
        # Entity involved in a relationship with a keyword-mentioned entity
        for subj, verb, obj in relationships:
            if subj.lower() in kw_lower and obj.lower() == name_lower:
                score += 5
                reason = reason or f"{verb} {subj}"
            elif obj.lower() in kw_lower and subj.lower() == name_lower:
                score += 5
                reason = reason or f"{verb} {obj}"
        # Organizations/authorities always boost authority
        if meta.get("@type") == "Organization":
            score += 2
            reason = reason or "authority source"
        # MedicalCondition entities add expertise signals
        if meta.get("@type") == "MedicalCondition":
            score += 1
            reason = reason or "expertise signal"

        scored.append({"name": name, "type": meta["@type"], "score": score, "reason": reason})

    scored.sort(key=lambda x: -x["score"])

    # Primary: top entities with score > 0 (max 5)
    primary = [{"name": s["name"], "type": s["type"], "reason": s["reason"]}
               for s in scored if s["score"] > 0][:5]
    # Secondary: next batch (max 5)
    secondary = [{"name": s["name"], "type": s["type"]}
                 for s in scored if s["score"] == 0][:5]

    # If no keyword match, use all entities split evenly
    if not primary:
        primary = [{"name": s["name"], "type": s["type"], "reason": "niche core"}
                   for s in scored[:5]]
        secondary = [{"name": s["name"], "type": s["type"]} for s in scored[5:10]]

    # Relevant relationships: those involving any primary entity
    primary_names = {p["name"].lower() for p in primary}
    relevant_rels = [r for r in relationships
                     if r[0].lower() in primary_names or r[2].lower() in primary_names]

    return {"primary": primary, "secondary": secondary, "relationships": relevant_rels}
