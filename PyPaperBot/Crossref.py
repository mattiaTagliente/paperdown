from crossref_commons.iteration import iterate_publications_as_json
from crossref_commons.retrieval import get_entity
from crossref_commons.types import EntityType, OutputType
from .PapersFilters import similarStrings
from .Paper import Paper
import requests
import time
import random


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
    paper_found = Paper()
    paper_found.DOI = DOI
    
    try:
        paper = get_entity(DOI, EntityType.PUBLICATION, OutputType.JSON)
        if paper is not None and len(paper) > 0:
            if "title" in paper:
                paper_found.title = paper["title"][0]
            if "short-container-title" in paper and len(paper["short-container-title"]) > 0:
                paper_found.jurnal = paper["short-container-title"][0]

            if restrict is None or restrict != 1:
                paper_found.setBibtex(getBibtex(paper_found.DOI))
    except:
        print("Paper not found " + DOI)

    return paper_found


# Get paper information from Crossref and return a list of Paper
def getPapersInfo(papers, scholar_search_link, restrict, scholar_results):
    """
    This function is now updated to accept a list of Paper objects and enrich
    them with metadata from Crossref, rather than expecting a list of dictionaries.
    """
    num = 1
    for paper_obj in papers:
        # Use the title from the existing Paper object
        title = paper_obj.title
        if not title: continue
        queries = {'query.bibliographic': title.lower(), 'sort': 'relevance', "select": "DOI,title,deposited,author,short-container-title"}
        print(f"Searching paper {num} of {len(papers)} on Crossref... ('{title[:40]}...')")
        num += 1

        found_timestamp = 0
        
        try:
            for el in iterate_publications_as_json(max_results=30, queries=queries):
                el_date = 0
                if "deposited" in el and "timestamp" in el["deposited"]:
                    el_date = int(el["deposited"]["timestamp"])

                # Compare found title with the paper object's title
                if (paper_obj.DOI is None or el_date > found_timestamp) and "title" in el and similarStrings(
                        title.lower(), el["title"][0].lower()) > 0.75:
                    
                    found_timestamp = el_date

                    # Enrich the existing paper object instead of creating a new one
                    if "DOI" in el:
                        paper_obj.DOI = el["DOI"].strip().lower()
                    if "short-container-title" in el and len(el["short-container-title"]) > 0:
                        paper_obj.jurnal = el["short-container-title"][0]

                    if (restrict is None or restrict != 1) and paper_obj.DOI:
                        paper_obj.setBibtex(getBibtex(paper_obj.DOI))

            # Brief pause to respect API rate limits
            time.sleep(0.5 + random.random()) # Faster sleep time

        except ConnectionError as e:
            print(f"Connection error while searching for '{title}'. Waiting and trying again. Error: {e}")
            time.sleep(5)
        except Exception as e:
            print(f"An unexpected error occurred while searching for '{title}'. Error: {e}")

    # Return the original list, now enriched with data
    return papers