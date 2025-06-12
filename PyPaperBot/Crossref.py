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

# This cache is now keyed by a normalized title, as the final citekey isn't ready yet.
CACHE_FILE = os.path.join(os.getcwd(), 'cache', 'crossref_metadata_cache.json')
CACHE_EXPIRATION_SECONDS = 365 * 24 * 60 * 60

def normalize_title(title):
    if not title: return None
    return re.sub(r'[\W_]+', '', title.lower())

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f: return json.load(f)
        except (json.JSONDecodeError, IOError): return {}
    return {}

def save_cache(cache_data):
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

def getPapersInfoFromDOIs(DOI, restrict):
    """
    Gets paper metadata for a single DOI. This is used for the --doi and --doi-file CLI options.
    """
    paper_found = Paper()
    paper_found.DOI = DOI
    try:
        paper_info = get_entity(DOI, EntityType.PUBLICATION, OutputType.JSON)
        if paper_info and "title" in paper_info:
            paper_found.title = paper_info["title"][0]
        
        if paper_info and "author" in paper_info:
            authors = [f"{author.get('family', '')}, {author.get('given', '')}".strip() for author in paper_info.get('author', [])]
            paper_found.authors = "; ".join(authors)
        if paper_info and "created" in paper_info:
            paper_found.year = paper_info.get('created', {}).get('date-parts', [[None]])[0][0]

        if not restrict or restrict != 1:
            bibtex_str = getBibtex(paper_found.DOI)
            if bibtex_str:
                paper_found.setBibtex(bibtex_str)
    except Exception as e:
        print(f"Paper not found for DOI {DOI}. Reason: {e}")
    return paper_found

def getPapersInfo(papers, s2_api_key):
    """
    Enriches papers with authoritative metadata from Crossref.
    Crucially, it fetches the full author list, overwriting the temporary one from Scholar.
    """
    cache = load_cache()
    
    for i, p in enumerate(papers):
        title_key = normalize_title(p.title)
        if not title_key: continue

        print(f"[{i+1}/{len(papers)}] Processing: '{p.title[:40]}...'")
        
        if title_key in cache and time.time() - cache[title_key].get('timestamp', 0) < CACHE_EXPIRATION_SECONDS:
            print("    -> Found fresh data in cache.")
            cached_data = cache[title_key]
            p.DOI = cached_data.get("DOI")
            p.authors = cached_data.get("authors") # Load authoritative authors
            p.bibtex = cached_data.get("bibtex")
            if p.bibtex: p.setBibtex(p.bibtex)
            continue

        print("    -> No cache hit, querying APIs...")
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
                # Overwrite author info with authoritative data from Crossref
                if 'author' in best_match and best_match['author']:
                    author_list = [f"{a.get('family', '')}, {a.get('given', '')}".strip() for a in best_match['author'] if a.get('family')]
                    if author_list:
                        p.authors = "; ".join(author_list)

                if best_match.get("DOI"):
                    p.DOI = best_match.get("DOI").strip().lower()
                    p.setBibtex(getBibtex(p.DOI))
            else:
                print("    -> No confident match found on Crossref.")

        except Exception as e:
            print(f"    An unexpected Crossref error occurred: {e}")

        enrich_paper_with_abstract(p, s2_api_key)
        
        cache[title_key] = {
            'timestamp': time.time(),
            'DOI': p.DOI,
            'authors': p.authors,
            'bibtex': p.bibtex
        }
        time.sleep(0.5)

    save_cache(cache)
    return papers