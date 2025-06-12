# PyPaperBot/Crossref.py
from crossref_commons.iteration import iterate_publications_as_json
from crossref_commons.retrieval import get_entity
from crossref_commons.types import EntityType, OutputType
from .PapersFilters import similarStrings
from .Paper import Paper
from .MetadataFetcher import enrich_paper_with_abstract
import requests
import time
import os
import json
import re
import bibtexparser

CACHE_FILE = os.path.join(os.getcwd(), 'cache', 'crossref_metadata_cache.json')
CACHE_EXPIRATION_SECONDS = 365 * 24 * 60 * 60 # Cache for one year

def normalize_title(title):
    """Provides a consistent, simplified key for title comparisons."""
    if not title: return None
    return re.sub(r'[\W_]+', '', title.lower())

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f: return json.load(f)
        except (json.JSONDecodeError, IOError): return {}
    return {}

def save_cache(cache_data):
    """Saves the provided dictionary to the cache file."""
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, 'w') as f: json.dump(cache_data, f, indent=4)

def getBibtex(DOI):
    try:
        url_bibtex = f"https://api.crossref.org/works/{DOI}/transform/application/x-bibtex"
        x = requests.get(url_bibtex, timeout=15)
        x.raise_for_status()
        return str(x.text)
    except requests.exceptions.RequestException:
        return ""

def getPapersInfo(papers, s2_api_key):
    """
    Enriches papers with metadata from Crossref.
    It reads the cache by searching for a matching title, making it robust against key changes.
    """
    cache = load_cache()
    
    for i, p in enumerate(papers):
        print(f"[{i+1}/{len(papers)}] Processing: '{p.title[:40]}...'")
        
        is_cached = False
        paper_title_key = normalize_title(p.title)
        
        # --- ROBUST CACHE READING LOGIC ---
        for cached_item in cache.values():
            # First, try to use the modern 'normalized_title' field
            cached_title_key = cached_item.get("normalized_title")
            
            # If it's not there, fall back to parsing the bibtex from an old cache entry
            if not cached_title_key and "bibtex" in cached_item:
                try:
                    bib_db = bibtexparser.loads(cached_item["bibtex"])
                    if bib_db.entries:
                        cached_title_key = normalize_title(bib_db.entries[0].get('title'))
                except Exception:
                    continue # Could not parse bibtex, skip this cached item
            
            if paper_title_key == cached_title_key:
                if time.time() - cached_item.get('timestamp', 0) < CACHE_EXPIRATION_SECONDS:
                    print("    -> Found fresh data in cache.")
                    p.DOI = cached_item.get("DOI")
                    p.authors = cached_item.get("authors")
                    p.bibtex = cached_item.get("bibtex")
                    if p.bibtex: p.setBibtex(p.bibtex)
                    is_cached = True
                    break
        
        if is_cached:
            continue

        print("    -> No cache hit, querying APIs...")
        # (The rest of the function remains the same)
        try:
            best_match = None
            highest_similarity = 0.8
            queries = {'query.bibliographic': p.title.lower(), 'sort': 'relevance'}
            for el in iterate_publications_as_json(max_results=5, queries=queries):
                if "title" in el:
                    similarity = similarStrings(p.title.lower(), el["title"][0].lower())
                    if similarity > highest_similarity:
                        highest_similarity = similarity
                        best_match = el
            
            if best_match:
                if 'author' in best_match and best_match['author']:
                    author_list = [f"{a.get('family', '')}, {a.get('given', '')}".strip() for a in best_match['author'] if a.get('family')]
                    if author_list: p.authors = "; ".join(author_list)
                if best_match.get("DOI"):
                    p.DOI = best_match.get("DOI").strip().lower()
                    p.setBibtex(getBibtex(p.DOI))
            else:
                print("    -> No confident match found on Crossref.")
        except Exception as e:
            print(f"    An unexpected Crossref error occurred: {e}")

        enrich_paper_with_abstract(p, s2_api_key)
        time.sleep(0.5)

    return papers

def save_papers_to_cache(papers_list):
    """
    Saves a list of paper objects to the cache using their definitive citekey as the key
    and includes a normalized title for future lookups.
    """
    print("\nUpdating metadata cache with definitive citekeys...")
    if not papers_list:
        return
        
    cache = load_cache()
    
    for p in papers_list:
        if not p.citekey:
            print(f"    Warning: Cannot cache paper without a citekey ('{p.title[:30]}...').")
            continue
            
        cache[p.citekey] = {
            'timestamp': time.time(),
            'DOI': p.DOI,
            'authors': p.authors,
            'bibtex': p.bibtex,
            'normalized_title': normalize_title(p.title)
        }

    save_cache(cache)
    print("Cache update complete.")

def getPapersInfoFromDOIs(DOI, restrict):
    # This function remains unchanged
    paper_found = Paper()
    paper_found.DOI = DOI
    try:
        paper_info = get_entity(DOI, EntityType.PUBLICATION, OutputType.JSON)
        if paper_info and "title" in paper_info: paper_found.title = paper_info["title"][0]
        if paper_info and "author" in paper_info:
            authors = [f"{author.get('family', '')}, {author.get('given', '')}".strip() for author in paper_info.get('author', [])]
            paper_found.authors = "; ".join(authors)
        if paper_info and "created" in paper_info: paper_found.year = paper_info.get('created', {}).get('date-parts', [[None]])[0][0]
        if not restrict or restrict != 1:
            bibtex_str = getBibtex(paper_found.DOI)
            if bibtex_str: paper_found.setBibtex(bibtex_str)
    except Exception as e:
        print(f"Paper not found for DOI {DOI}. Reason: {e}")
    return paper_found