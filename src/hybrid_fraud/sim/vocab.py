"""Invented words for the synthetic world: sectors, payees, memos, tickets.

Every name is fictional. Generated text is cleaner than real attacker text;
the results memo says so.
"""

# Sector, MCC code, and what a legitimate business in it pays for.
SECTORS = [
    ("dental practice", "8021", ["dental supplies", "lab work", "office lease"]),
    ("software company", "5734", ["cloud hosting", "contractor", "software licence"]),
    ("event ticketing", "7922", ["stage rental", "venue deposit", "artist fee"]),
    ("grocery retailer", "5411", ["wholesale stock", "produce supplier", "cold storage"]),
    ("electronics distributor", "5065", ["component order", "freight", "customs duty"]),
    ("courier service", "4215", ["fuel", "vehicle lease", "subcontractor"]),
    ("medical clinic", "8011", ["equipment", "locum cover", "consumables"]),
]

# The vendors a real business in each sector pays. Many merchants share them.
LEGIT_PAYEE = {
    "dental practice": ["Patterson Dental Supply", "Chennai Lab Works", "Anna Nagar Properties"],
    "software company": ["AWS Cloud Services", "R. Kumar Consulting", "Atlassian Pty Ltd"],
    "event ticketing": ["LiveSound Stage Rentals", "Marina Hall Trust", "Rhythm Artist Mgmt"],
    "grocery retailer": ["Koyambedu Wholesale Mart", "GreenLeaf Produce", "ColdChain Storage"],
    "electronics distributor": ["Shenzhen Component Co", "BlueDart Freight", "Customs Clearing House"],
    "courier service": ["Indian Oil Fleet", "Wheels Vehicle Lease", "SpeedLine Subcontractors"],
    "medical clinic": ["MedEquip Systems", "Dr S. Rao Locum", "SteriCare Consumables"],
}

# Wrong for the business paying them, not wrong in themselves.
SUSPECT_PAYEE = [
    "CryptoBridge Holdings LLC", "Global Trade Settlement Ltd", "Apex Digital Ventures",
    "Meridian Capital Partners", "NovaPay Solutions Inc",
]
SUSPECT_MEMO = [
    "urgent liquidity transfer", "payment on account", "consulting services",
    "settlement transfer", "invoice settlement",
]
BENIGN_MEMO = ["Inv #{n} {purpose}", "{purpose} - monthly account", "PO-{n} {purpose}", "{purpose} ({n})"]

NAME_PREFIX = ["Northgate", "Bluewater", "Redfern", "Oakline", "Harbourview", "Silverleaf", "Kestrel", "Marlow"]
CITIES = ["Chennai", "Leeds", "Austin", "Rotterdam", "Brisbane", "Toronto", "Lagos", "Pune"]

KYB_TEMPLATES = [
    "{name} operates as a {sector} based in {city}, registered {year}. Revenue comes from local customers; "
    "owner-managed with two directors on file.",
    "{name} is a {sector} in {city} (registered {year}). Business licence and tax number verified at onboarding.",
    "{name}, {city}. Principal activity: {sector}. Registered {year}. Bank account held in the company name.",
]

TICKET_TEXT = {
    "2fa": [
        "Please reset two-factor authentication on our account, we changed phones.",
        "Our authenticator app stopped working, can you disable 2FA for the admin user?",
    ],
    "credential": [
        "Locked out of the dashboard, need a password reset urgently.",
        "Please update the login email on the account, the old mailbox is gone.",
    ],
    "billing": ["Question about last month's fee statement.", "Can you resend the March invoice?"],
    "other": ["How do I download a settlement report?", "Where can I change our logo?"],
}
