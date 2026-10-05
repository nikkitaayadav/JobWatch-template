"""Loads config/filters.json: the search keywords and pre-screen settings for the fetchers."""
import json, os, re
PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "filters.json")
F = json.load(open(PATH))
def skills(key="skill_terms"): return re.compile(r"\b(" + F[key] + r")\b", re.I)
