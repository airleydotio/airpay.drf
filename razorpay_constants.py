BUSINESS_TYPE = [
    ('individual', 'Individual'),
    ('llp', 'LLP'),
    ('private_limited', 'Private Limited'),
    ('public_limited', 'Public Limited'),
    ('partnership', 'Partnership'),
    ('proprietorship', 'Proprietorship'),
    ('trust', 'Trust'),
    ('society', 'Society'),
    ('not_yet_registered', 'Not Yet Registered'),
    ('educational_institutes', 'Educational Institutes'),
    ('ngo', 'NGO'),
]

BUSINESS_CATEGORY = [
    ('financial_services', 'Financial Services'),
    ('education', 'Education'),
    ('healthcare', 'Healthcare'),
    ('utilities', 'Utilities'),
    ('government', 'Government'),
    ('logistics', 'Logistics'),
    ('tours_and_travel', 'Tours and Travel'),
    ('transport', 'Transport'),
    ('ecommerce', 'Ecommerce'),
    ('food', 'Food'),
    ('it_and_software', 'IT and Software'),
    ('gaming', 'Gaming'),
    ('media_and_entertainment', 'Media and Entertainment'),
    ('services', 'Services'),
    ('housing', 'Housing'),
    ('not_for_profit', 'Not For Profit'),
    ('social', 'Social'),
    ('others', 'Others'),
]

KYC_DOCUMENTS = {
    'owner_pan': {
        'api_name': 'stakeholder',
        'required': True,
        'business_types': ['individual', 'proprietorship', 'not_yet_registered'],
        'document_type': 'pan',
        'document_name': 'Owner PAN/Signatory PAN',
        'description': 'Owner PAN/Signatory PAN',
        'number': 1,
    },
    'business_pan': {
        'api_name': 'linked_account_onboarding',
        'required': True,

        'business_types': ['proprietorship', 'public_limited', 'private_limited', 'llp', 'partnership', 'trust', 'ngo',
                           'society', 'educational_institutes'],
        'document_type': 'pan',
        'document_name': 'Business PAN',
        'description': 'Business PAN',
        'number': 1,
    },
    'bank_account': {
        'api_name': 'product_configuration',
        'required': True,
        'business_types': ['individual', 'proprietorship', 'public_limited', 'private_limited', 'llp', 'partnership',
                           'trust', 'ngo', 'society', 'educational_institutes', 'not_yet_registered'],
        'document_type': 'bank_account',
        'document_name': 'Bank Account',
        'description': 'Bank Account',
        'number': 1,
    },
    'gst': {
        'api_name': 'linked_account_onboarding',
        'required': True,
        'business_types': ['proprietorship', 'public_limited', 'private_limited', 'llp', 'partnership', 'trust', 'ngo',
                           'society', 'educational_institutes'],
        'document_type': 'gst',
        'document_name': 'GST',
        'description': 'GST',
        'number': 1,
    },
}

BUSINESS_SUB_CATEGORY = {
    'financial_services': [
        "mutual_fund", "lending", "cryptocurrency", "insurance",
        "nbfc", "cooperatives", "pension_fund", "forex",
        "securities", "commodities", "accounting", "financial_advisor",
        "crowdfunding", "trading", "betting", "get_rich_schemes",
        "moneysend_funding", "wire_transfers_and_money_orders",
        "tax_preparation_services", "tax_payments", "digital_goods", "atms"
    ],
    'education': [
        'college', 'schools', 'university', 'professional_courses', 'distance_learning', 'day_care', 'coaching',
        'elearning', 'vocational_and_trade_schools', 'sporting_clubs', 'dance_halls_studios_and_schools',
        'correspondence_schools'],
    'healthcare': [
        "pharmacy", "clinic", "hospital", "lab", "dietician",
        "fitness", "health_coaching", "health_products", "drug_stores",
        "healthcare_marketplace", "osteopaths", "medical_equipment_and_supply_stores",
        "podiatrists_and_chiropodists", "dentists_and_orthodontists", "hardware_stores",
        "ophthalmologists", "orthopedic_goods_stores", "testing_laboratories",
        "doctors", "health_practitioners_medical_services", "testing_laboratories"
    ],
    'ecommerce': [
        "ecommerce_marketplace", "agriculture", "books", "electronics_and_furniture",
        "coupons", "rental", "fashion_and_lifestyle", "gifting", "grocery",
        "baby_products", "office_supplies", "wholesale", "religious_products",
        "pet_products", "sports_products", "arts_and_collectibles",
        "sexual_wellness_products", "drop_shipping", "crypto_machinery",
        "tobacco", "weapons_and_ammunitions", "stamps_and_coins_stores",
        "office_equipment", "automobile_parts_and_equipements", "garden_supply_stores",
        "household_appliance_stores", "non_durable_goods", "pawn_shops",
        "electrical_parts_and_equipment", "wig_and_toupee_shops",
        "gift_novelty_and_souvenir_shops", "duty_free_stores",
        "office_and_commercial_furniture", "dry_goods", "books_and_publications",
        "camera_and_photographic_stores", "record_shops", "meat_supply_stores",
        "leather_goods_and_luggage", "snowmobile_dealers",
        "men_and_boys_clothing_stores", "paint_supply_stores", "automotive_parts",
        "jewellery_and_watch_stores", "auto_store_home_supply_stores",
        "tent_stores", "shoe_stores_retail", "petroleum_and_petroleum_products",
        "department_stores", "automotive_tire_stores", "sport_apparel_stores",
        "variety_stores", "chemicals_and_allied_products", "commercial_equipments",
        "fireplace_parts_and_accessories", "family_clothing_stores",
        "fabric_and_sewing_stores", "home_supply_warehouse", "art_supply_stores",
        "camper_recreational_and_utility_trailer_dealers", "clocks_and_silverware_stores",
        "discount_stores", "school_supplies_and_stationery", "second_hand_stores",
        "watch_and_jewellery_repair_stores", "liquor_stores", "boat_dealers",
        "opticians_optical_goods_and_eyeglasse_stores", "wholesale_footwear_stores",
        "cosmetic_stores", "home_furnishing_stores", "antique_stores",
        "plumbing_and_heating_equipment", "telecommunication_equipment_stores",
        "women_clothing", "florists", "computer_software_stores",
        "building_matrial_stores", "candy_nut_confectionery_shops",
        "glass_and_wallpaper_stores", "commercial_photography_and_graphic_design_services",
        "video_game_supply_stores", "fuel_dealers", "drapery_and_window_coverings_stores",
        "hearing_aids_stores", "automotive_paint_shops", "durable_goods_stores",
        "uniforms_and_commercial_clothing_stores", "fur_shops", "industrial_supplies",
        "bicycle_stores", "second_hand_stores", "motorcycle_shops_and_dealers",
        "children_and_infants_wear_stores", "women_accessory_stores",
        "construction_materials", "books_periodicals_and_newspaper",
        "floor_covering_stores", "crystal_and_glassware_stores",
        "accessory_and_apparel_stores", "hardware_equipment_and_supply_stores",
        "computers_peripheral_equipment_software", "automobile_and_truck_dealers",
        "aircraft_and_farm_equipment_dealers", "antique_shops_sales_and_repairs",
        "hearing_aids_stores", "music_stores", "furniture_and_home_furnishing_store"
    ],
    'services': [
        "repair_and_cleaning", "interior_design_and_architect", "movers_and_packers",
        "legal", "event_planning", "service_centre", "consulting",
        "ad_and_marketing", "services_classifieds", "multi_level_marketing",
        "construction_services", "architectural_services", "car_washes",
        "motor_home_rentals", "stenographic_and_secretarial_support_services",
        "chiropractors", "automotive_service_shops", "shoe_repair_shops",
        "telecommunication_service", "fines", "security_agencies", "tailors",
        "type_setting_and_engraving_services", "small_appliance_repair_shops",
        "photography_labs", "dry_cleaners", "massage_parlors",
        "electronic_repair_shops", "cleaning_and_sanitation_services",
        "nursing_care_facilities", "direct_marketing", "lottery",
        "veterinary_services", "affliated_auto_rental", "alimony_and_child_support",
        "airport_flying_fields", "golf_courses", "tire_retreading_and_repair_shops",
        "television_cable_services", "recreational_and_sporting_camps",
        "barber_and_beauty_shops", "agricultural_cooperatives",
        "carpentry_contractors", "wrecking_and_salvaging_services",
        "automobile_towing_services", "video_tape_rental_stores",
        "miscellaneous_repair_shops", "motor_homes_and_parts", "horse_or_dog_racing",
        "laundry_services", "electrical_contractors",
        "debt_marriage_personal_counseling_service",
        "air_conditioning_and_refrigeration_repair_shops",
        "credit_reporting_agencies", "heating_and_plumbing_contractors",
        "carpet_and_upholstery_cleaning_services", "swimming_pools",
        "roofing_and_metal_work_contractors", "internet_service_providers",
        "recreational_camps", "masonry_contractors",
        "exterminating_and_disinfecting_services", "ambulance_services",
        "funeral_services_and_crematories", "metal_service_centres",
        "copying_and_blueprinting_services", "fuel_dispensers", "welding_repair",
        "mobile_home_dealers", "concrete_work_contractors", "boat_rentals",
        "personal_shoppers_and_shopping_clubs", "door_to_door_sales",
        "travel_related_direct_marketing", "lottery_and_betting",
        "bands_orchestras_and_miscellaneous_entertainers",
        "furniture_repair_and_refinishing", "contractors",
        "direct_marketing_and_subscription_merchants",
        "typewriter_stores_sales_service_and_rentals", "recreation_services",
        "direct_marketing_insurance_services", "business_services",
        "inbound_telemarketing_merchants", "public_warehousing",
        "outbound_telemarketing_merchants", "clothing_rental_stores",
        "transportation_services", "electric_razor_stores", "service_stations",
        "photographic_studio", "professional_services"
    ],
    'housing': [
        "developer", "facility_management", "rwa", "coworking",
        "realestate_classifieds", "space_rental"
    ],
    'not_for_profit': [
        "charity", "educational", "religious", "personal"
    ],
    'social': [
        "matchmaking", "social_network", "messaging", "professional_network",
        "neighbourhood_network", "political_organizations",
        "automobile_associations_and_clubs", "country_and_athletic_clubs",
        "associations_and_membership"
    ],
    'media_and_entertainment': [
        "video_on_demand", "music_streaming", "multiplex",
        "content_and_publishing", "ticketing", "news", "video_game_arcades",
        "video_tape_production_and_distribution", "bowling_alleys",
        "billiard_and_pool_establishments", "amusement_parks_and_circuses",
        "ticket_agencies"
    ],
    'gaming': [
        "game_developer", "esports", "online_casino", "fantasy_sports",
        "gaming_marketplace"
    ],
    'it_and_software': [
        "saas", "paas", "iaas", "consulting_and_outsourcing",
        "web_development", "technical_support", "data_processing"
    ],
    'food': [
        "online_food_ordering", "restaurant", "food_court", "catering",
        "alcohol", "restaurant_search_and_booking", "dairy_products", "bakeries"
    ],
    'utilities': [
        "electricity", "gas", "telecom", "water", "cable", "broadband",
        "dth", "internet_provider", "bill_and_recharge_aggregators"
    ],
    'government': [
        "central", "state", "intra_government_purchases", "goverment_postal_services"
    ],
    'logistics': [
        "freight", "courier", "warehousing", "distribution",
        "end_to_end_logistics", "courier_services"
    ],
    'tours_and_travel': [
        "aviation", "accommodation", "ota", "travel_agency",
        "tourist_attractions_and_exhibits", "timeshares",
        "aquariums_dolphinariums_and_seaquariums"
    ],
    'transport': [
        "cab_hailing", "bus", "train_and_metro", "automobile_rentals",
        "cruise_lines", "parking_lots_and_garages", "transportation",
        "bridge_and_road_tolls", "freight_transport",
        "truck_and_utility_trailer_rentals"
    ],
}
