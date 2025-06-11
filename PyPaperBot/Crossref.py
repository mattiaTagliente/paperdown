# PyPaperBot/Crossref.py
from crossref_commons.iteration import iterate_publications_as_json
from crossref_commons.retrieval import get_entity
from crossref_commons.types import EntityType, OutputType
from .PapersFilters import similarStrings
from .Paper import Paper
from .MetadataFetcher import enrich_paper_with_abstract
import requests
import time
import random
import os
import json
import re

CACHE_FILE = os.path.join(os.getcwd(), 'cache', 'crossref_cache.json')
CACHE_EXPIRATION_SECONDS = 365 * 24 * 60 * 60  # One year

def normalize_title(title):
    if not title:
        return None
    return re.sub(r'[\W_]+', '', title.lower())

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_cache(cache_data):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache_data, f, indent=4)

def getBibtex(DOI):
    try:
        url_bibtex = f"https://api.crossref.org/works/{DOI}/transform/application/x-bibtex"
        x = requests.get(url_bibtex)
        x.raise_for_status()
        return str(x.text)
    except requests.exceptions.RequestException:
        return ""

def getPapersInfoFromDOIs(DOI, restrict):
    paper_found = Paper()
    paper_found.DOI = DOI
    try:
        paper = get_entity(DOI, EntityType.PUBLICATION, OutputType.JSON)
        if paper and "title" in paper:
            paper_found.title = paper["title"][0]
        if paper and "short-container-title" in paper and paper["short-container-title"]:
            paper_found.jurnal = paper["short-container-title"][0]
        if not restrict or restrict != 1:
            bibtex_str = getBibtex(paper_found.DOI)
            if bibtex_str:
                paper_found.setBibtex(bibtex_str)
    except Exception:
        print("Paper not found for DOI: " + DOI)
    return paper_found

def getPapersInfo(papers, scholar_search_link, restrict, s2_api_key):
    cache = load_cache()
    
    for i, paper_obj in enumerate(papers):
        title_key = normalize_title(paper_obj.title)
        if not title_key:
            continue

        print(f"[{i+1}/{len(papers)}] Processing: '{paper_obj.title[:40]}...'")

        if title_key in cache:
            cached_item = cache[title_key]
            if time.time() - cached_item.get('timestamp', 0) < CACHE_EXPIRATION_SECONDS:
                print("    -> Found fresh data in cache.")
                paper_obj.DOI = cached_item.get('DOI')
                paper_obj.jurnal = cached_item.get('jurnal')
                if 'bibtex' in cached_item:
                    paper_obj.setBibtex(cached_item['bibtex'])
                continue

        print("    -> No cache hit, querying APIs...")
        
        try:
            best_match = None
            highest_similarity = 0.8
            queries = {'query.bibliographic': paper_obj.title.lower(), 'sort': 'relevance'}
            for el in iterate_publications_as_json(max_results=5, queries=queries):
                if "title" in el:
                    similarity = similarStrings(paper_obj.title.lower(), el["title"][0].lower())
                    if similarity > highest_similarity:
                        highest_similarity = similarity
                        best_match = el
            
            if best_match:
                paper_obj.DOI = best_match.get("DOI", "").strip().lower()
                bibtex_str = getBibtex(paper_obj.DOI)
                if bibtex_str:
                    paper_obj.setBibtex(bibtex_str)
                    
                    enrich_paper_with_abstract(paper_obj, s2_api_key)
                    
                    cache[title_key] = {
                        'timestamp': time.time(),
                        'DOI': paper_obj.DOI,
                        'jurnal': paper_obj.jurnal,
                        'bibtex': paper_obj.bibtex
                    }
                    save_cache(cache)
            else:
                print("    -> No confident match found on Crossref.")

            time.sleep(0.5)

        except Exception as e:
            print(f"    An unexpected error occurred: {e}")

    return papers