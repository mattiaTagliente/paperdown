# PyPaperBot/MetadataFetcher.py
import requests
import re
import html

def strip_xml(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()

def insert_abstract(bibtex: str, abs_text: str) -> str:
    # Cleans up the abstract text for BibTeX
    abs_text = re.sub(r'\s+', ' ', abs_text).strip()
    field = f"  abstract = {{{abs_text}}},\n"
    # Injects the abstract field before the final closing brace
    return re.sub(r"\n}$", f"\n{field}}}", bibtex, count=1)

def enrich_paper_with_abstract(paper, s2_api_key=None):
    """
    Enriches a Paper object's bibtex with an abstract if it's missing.
    Tries Semantic Scholar first, then Crossref's JSON API.
    """
    if not paper.bibtex or (paper.bibtex and 'abstract =' in paper.bibtex.lower()):
        return # Skip if no bibtex or abstract already exists

    print(f"    -> Abstract missing for '{paper.title[:30]}...'. Searching...")
    abstract_txt = None
    
    # Strategy 1: Semantic Scholar API (if key is provided)
    if s2_api_key:
        paper_id = ("DOI:" + paper.DOI) if paper.DOI else ("ARXIV:" + paper.scholar_link) # Simplified ID
        try:
            headers = {"x-api-key": s2_api_key}
            s2 = requests.get(
                f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}",
                params={"fields": "abstract"},
                headers=headers, timeout=10
            )
            if s2.status_code == 200:
                js = s2.json()
                abstract_txt = js.get("abstract", "").strip() or None
                if abstract_txt: print("        Found abstract on Semantic Scholar.")
        except Exception:
            pass # Fail silently and try next method

    # Strategy 2: Crossref JSON API Fallback
    if not abstract_txt and paper.DOI:
        try:
            cr = requests.get(f"https://api.crossref.org/works/{paper.DOI}", timeout=10).json()
            raw_abs = cr["message"].get("abstract")
            if raw_abs:
                abstract_txt = strip_xml(raw_abs)
                if abstract_txt: print("        Found abstract on Crossref.")
        except Exception:
            pass # Fail silently

    # Inject the abstract into the bibtex string if found
    if abstract_txt:
        paper.bibtex = insert_abstract(paper.bibtex, abstract_txt)