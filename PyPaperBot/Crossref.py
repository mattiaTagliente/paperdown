from crossref_commons.iteration import iterate_publications_as_json
from crossref_commons.retrieval import get_entity
from crossref_commons.types import EntityType, OutputType
from .PapersFilters import similarStrings
from .Paper import Paper
import requests
import time
import random
import os
import json
import re

CACHE_FILE = os.path.join(os.getcwd(), 'cache', 'crossref_cache.json')
CACHE_EXPIRATION_SECONDS = 365 * 24 * 60 * 60  # One year

def normalize_title(title):
    """Creates a consistent key for caching based on the paper title."""
    if not title:
        return None
    return re.sub(r'[\W_]+', '', title.lower())

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_cache(cache_data):
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache_data, f, indent=4)

def getBibtex(DOI):
    try:
        url_bibtex = "http://api.crossref.org/works/" + DOI + "/transform/application/x-bibtex"
        x = requests.get(url_bibtex)
        if x.status_code == 404:
            return ""
        return str(x.text)
    except Exception as e:
        print(e)
        return ""


def getPapersInfoFromDOIs(DOI, restrict):
    # This function is for single DOI lookups and can largely remain as is.
    paper_found = Paper()
    paper_found.DOI = DOI
    try:
        paper = get_entity(DOI, EntityType.PUBLICATION, OutputType.JSON)
        if paper and "title" in paper:
            paper_found.title = paper["title"][0]
        if paper and "short-container-title" in paper and paper["short-container-title"]:
            paper_found.jurnal = paper["short-container-title"][0]
        if not restrict or restrict != 1:
            paper_found.setBibtex(getBibtex(paper_found.DOI))
    except Exception:
        print("Paper not found " + DOI)
    return paper_found


def getPapersInfo(papers, scholar_search_link, restrict, scholar_results):
    """
    Enriches Paper objects with metadata from Crossref, using a title-based cache.
    """
    cache = load_cache()
    
    for i, paper_obj in enumerate(papers):
        title_key = normalize_title(paper_obj.title)
        if not title_key:
            continue

        print(f"[{i+1}/{len(papers)}] Processing metadata for: '{paper_obj.title[:40]}...'")

        # Check cache using the normalized title
        if title_key in cache:
            cached_item = cache[title_key]
            cache_age = time.time() - cached_item.get('timestamp', 0)
            if cache_age < CACHE_EXPIRATION_SECONDS:
                print("    -> Found fresh data in cache.")
                # Populate paper object from cache
                paper_obj.DOI = cached_item.get('DOI')
                paper_obj.jurnal = cached_item.get('jurnal')
                if (not restrict or restrict != 1) and 'bibtex' in cached_item:
                    paper_obj.setBibtex(cached_item['bibtex'])
                continue  # Move to the next paper

        # If not in cache or stale, query the API
        print("    -> No cache hit, querying Crossref...")
        queries = {'query.bibliographic': paper_obj.title.lower(), 'sort': 'relevance', "select": "DOI,title,deposited,author,short-container-title"}
        
        try:
            # Find the best match from Crossref
            best_match = None
            highest_similarity = 0.75 # Minimum threshold
            
            for el in iterate_publications_as_json(max_results=5, queries=queries):
                if "title" in el:
                    similarity = similarStrings(paper_obj.title.lower(), el["title"][0].lower())
                    if similarity > highest_similarity:
                        highest_similarity = similarity
                        best_match = el
            
            if best_match:
                paper_obj.DOI = best_match.get("DOI", "").strip().lower()
                if "short-container-title" in best_match and best_match["short-container-title"]:
                    paper_obj.jurnal = best_match["short-container-title"][0]
                
                if (not restrict or restrict != 1) and paper_obj.DOI:
                    bibtex = getBibtex(paper_obj.DOI)
                    paper_obj.setBibtex(bibtex)
                    # Update cache with the new, validated data
                    cache[title_key] = {
                        'timestamp': time.time(),
                        'DOI': paper_obj.DOI,
                        'jurnal': paper_obj.jurnal,
                        'bibtex': bibtex
                    }
            else:
                print("    -> No confident match found on Crossref.")

            time.sleep(0.5 + random.random())

        except Exception as e:
            print(f"    An unexpected error occurred while searching Crossref: {e}")

    save_cache(cache)
    return papers