from pathlib import Path

import yaml


VALUES_PATH = Path(__file__).resolve().parents[1] / "skills" / "wardrobe_sql" / "references" / "values.yaml"
VALUES = yaml.safe_load(VALUES_PATH.read_text(encoding="utf-8"))
SEMANTIC_VERSION = VALUES["version"]
OUTERWEAR_SUB_CATEGORIES = frozenset(VALUES["outerwear_sub_categories"])


def synonym_map(section: str):
    return {
        key: tuple(item.get("synonyms", [])) if isinstance(item, dict) else tuple(item)
        for key, item in VALUES[section].items()
    }


SEASON_SYNONYMS = synonym_map("season")
OCCASION_SYNONYMS = synonym_map("occasion")
COLOR_SYNONYMS = synonym_map("color")
ROLE_SYNONYMS = synonym_map("garment_role")
STYLE_SYNONYMS = synonym_map("style")


def garment_role(item):
    category = item.get("category") or ""
    sub_category = item.get("sub_category") or item.get("subCategory") or ""
    if category == "套装":
        return "suit"
    if category == "下装":
        return "bottom"
    if category == "上装" and sub_category in OUTERWEAR_SUB_CATEGORIES:
        return "outerwear"
    if category == "上装":
        return "top"
    return "unknown"


def find_matching_keys(text, dictionary):
    return [
        key
        for key, words in dictionary.items()
        if key in text or any(word and word in text for word in words)
    ]


def detect_seasons(text):
    seasons = find_matching_keys(text, SEASON_SYNONYMS)
    for season in tuple(seasons):
        for included in VALUES["season"].get(season, {}).get("include", []):
            if included not in seasons:
                seasons.append(included)
    return seasons


def detect_occasions(text):
    return find_matching_keys(text, OCCASION_SYNONYMS)


def detect_colors(text):
    return find_matching_keys(text, COLOR_SYNONYMS)


def detect_roles(text):
    return find_matching_keys(text, ROLE_SYNONYMS)


def detect_styles(text):
    return find_matching_keys(text, STYLE_SYNONYMS)
