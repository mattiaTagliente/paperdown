# PyPaperBot/MetadataFetcher.py
import requests
import re
import html
import bibtexparser

def strip_xml(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()

def enrich_paper_with_abstract(paper, s2_api_key=None):
    """
    Enriches a Paper object's bibtex with an abstract if it's missing.
    Tries Semantic Scholar first, then Crossref's JSON API.
    """
    if not paper.bibtex or (paper.bibtex and 'abstract =' in paper.bibtex.lower()):
        return

    print(f"    -> Abstract missing for '{paper.title[:30]}...'. Searching...")
    abstract_txt = None

    # Strategy 1: Semantic Scholar API (if key is provided)
    if s2_api_key and paper.DOI:
        try:
            headers = {"x-api-key": s2_api_key}
            s2 = requests.get(
                f"https://api.semanticscholar.org/graph/v1/paper/DOI:{paper.DOI}",
                params={"fields": "abstract"},
                headers=headers, timeout=10
            )
            if s2.status_code == 200:
                js = s2.json()
                abstract_txt = js.get("abstract", "").strip() or None
                if abstract_txt: print("        Found abstract on Semantic Scholar.")
        except Exception:
            pass

    # Strategy 2: Crossref JSON API Fallback
    if not abstract_txt and paper.DOI:
        try:
            cr = requests.get(f"https://api.crossref.org/works/{paper.DOI}", timeout=10).json()
            raw_abs = cr["message"].get("abstract")
            if raw_abs:
                abstract_txt = strip_xml(raw_abs)
                if abstract_txt: print("        Found abstract on Crossref.")
        except Exception:
            pass

    # Inject the abstract into the bibtex string using the bibtexparser library
    if abstract_txt:
        try:
            parser = bibtexparser.bparser.BibTexParser(common_strings=True)
            bib_database = bibtexparser.loads(paper.bibtex, parser=parser)
            if bib_database.entries:
                # Add the abstract to the entry
                bib_database.entries[0]['abstract'] = abstract_txt
                # Write the updated entry back to the paper.bibtex string
                writer = bibtexparser.bwriter.BibTexWriter()
                writer.indent = '    '
                paper.bibtex = writer.write(bib_database)
                print("        Successfully added abstract to BibTeX entry.")
        except Exception as e:
            print(f"        Warning: Failed to inject abstract into BibTeX. Reason: {e}")