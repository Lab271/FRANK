"""
Data normalization mappings for FRANK core models.

These mappings enable forgiving input by normalizing common variations
of sector names and organization sizes to canonical values.
"""

# Sector normalization mappings
# Maps common sector name variations to canonical sector values
SECTOR_MAPPINGS = {
    "finance": "financial",
    "banking": "financial",
    "healthcare": "health",
    "medical": "health",
    "government": "public_sector",
    "gov": "public_sector",
    "tech": "technology",
    "it": "technology",
}

# Organization size normalization mappings
# Maps common size category variations to canonical size values
SIZE_MAPPINGS = {
    "small": "small",
    "sme": "small",
    "startup": "small",
    "medium": "medium",
    "mid": "medium",
    "large": "large",
    "enterprise": "large",
    "multinational": "large",
}
