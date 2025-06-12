# PyPaperBot/Downloader.py
from os import path
import os
import requests
import urllib3
import time
import shutil
import tempfile
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import undetected_chromedriver as uc
from unpywall import Unpywall
from .PapersFilters import similarStrings
from .HTMLparsers import getSchiHubPDF, SciHubUrls, get_scidb_pdf_link, scrape_page_for_pdf_link
from .NetInfo import NetInfo
from .Utils import URLjoin
from .GeminiDownloader import download_with_gemini_agent
import arxiv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def setSciHubUrl(session):
    """
    Dynamically finds a working Sci-Hub mirror.
    """
    print("Searching for a sci-hub mirror...")
    mirrors_url = "https://sci-hub.ee/"
    try:
        r = session.get(mirrors_url, headers=NetInfo.HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Select links that start with 'https://sci-hub.'
        links = [a['href'] for a in soup.select('a[href^="https://sci-hub."]')]
        
        for l in links:
            # Ensure the link ends correctly
            if not l.endswith('/'):
                l += '/'
            try:
                # Test the mirror by checking its title
                r_test = session.get(l, headers=NetInfo.HEADERS, timeout=10, verify=False)
                if r_test.status_code == 200 and "Sci-Hub" in r_test.text:
                    NetInfo.SciHub_URL = l
                    print(f"Using Sci-Hub mirror: {l}")
                    return
            except requests.exceptions.RequestException:
                continue
    except requests.exceptions.RequestException as e:
        print(f"    Could not fetch Sci-Hub mirrors: {e}")
    
    print("\nNo working Sci-Hub instance found! Using default.")
    NetInfo.SciHub_URL = "https://sci-hub.se/"


def getSaveDir(folder, fname):
    dir_ = path.join(folder, fname)
    n = 1
    while path.exists(dir_):
        n += 1
        dir_ = path.join(folder, f"({n}){fname}")
    return dir_

def get_arxiv_link(title, paper_obj):
    try:
        search = arxiv.Search(query=f'ti:"{title}"', max_results=1)
        result = next(search.results(), None)
        if result and similarStrings(result.title.lower(), title.lower()) > 0.8:
            return result.pdf_url
    except Exception as e:
        print(f"    arXiv search failed: {e}")
    return None

def saveFile(file_name, content, paper, dwn_source):
    try:
        with open(file_name, 'wb') as f:
            f.write(content)
        if path.exists(file_name) and os.path.getsize(file_name) > 1024:
            paper.downloaded = True
            paper.downloadedFrom = dwn_source
            print(f"    Success: Downloaded from {dwn_source}.")
            return True
        else:
            if path.exists(file_name): os.remove(file_name)
            print("    ERROR: File write failed or the file is too small.")
            return False
    except (IOError, PermissionError) as e:
        print(f"    ERROR: Could not save file. Reason: {e}")
        return False

def download_with_selenium_agent(url, final_file_path, paper_obj, source_name):
    print(f"    -> Trying browser fallback for {source_name}...")
    # This feature is currently disabled due to instability.
    return False

def downloadPapers(papers, dwnl_dir, num_limit, SciHub_URL=None, SciDB_URL=None, gemini_api_key=None):
    session = requests.Session()
    session.headers.update(NetInfo.HEADERS) # Use base headers
    NetInfo.gemini_api_key = gemini_api_key
    if not getattr(NetInfo, 'SciHub_URL', None):
        setSciHubUrl(session)

    for i, p in enumerate(papers):
        if (num_limit is not None and i >= num_limit) or p.downloaded:
            continue

        print(f"\n[{i+1}/{len(papers)}] Processing: {p.title[:60]}...")
        pdf_dir = getSaveDir(dwnl_dir, p.getFileName())

        # Strategy 1: Unpaywall
        print("--> Checking Unpaywall...")
        try:
            if p.DOI:
                unpaywall_url = Unpywall.get_doc_link(p.DOI)
                if unpaywall_url:
                    r = session.get(unpaywall_url, timeout=30, verify=False, allow_redirects=True)
                    if r.ok and 'application/pdf' in r.headers.get('content-type', '').lower():
                        if saveFile(pdf_dir, r.content, p, "Unpaywall"):
                            continue
                    elif r.ok and 'text/html' in r.headers.get('content-type', '').lower():
                        print("    -> Unpaywall returned an HTML page, attempting to find PDF link...")
                        scraped_link = scrape_page_for_pdf_link(r.text, r.url)
                        if scraped_link:
                            r_pdf = session.get(scraped_link, timeout=30, verify=False)
                            if r_pdf.ok and saveFile(pdf_dir, r_pdf.content, p, "Unpaywall (scraped)"):
                                continue
                    else:
                        print(f"    Unpaywall link did not return a valid PDF (Status: {r.status_code}).")
                else:
                    print("    No open access URL found on Unpaywall.")
            else:
                print("    Paper has no DOI, cannot check Unpaywall.")
        except Exception as e:
            print(f"    Unpaywall check failed with an error: {e}")
        
        # Strategy 2: Direct DOI link
        if not p.downloaded and p.DOI:
            print("--> Checking direct DOI link...")
            try:
                direct_url = f"https://doi.org/{p.DOI}"
                r = session.get(direct_url, headers=NetInfo.HEADERS, timeout=30, allow_redirects=True)
                if r.ok and 'application/pdf' in r.headers.get('content-type', '').lower():
                    if saveFile(pdf_dir, r.content, p, "Direct DOI"):
                        continue
                else:
                    print(f"    Direct DOI link did not resolve to a PDF (Status: {r.status_code}).")
            except Exception as e:
                print(f"    Direct DOI check failed with an error: {e}")

        # Strategy 3: arXiv
        if not p.downloaded:
            print("--> Checking arXiv...")
            try:
                arxiv_url = get_arxiv_link(p.title, p)
                if arxiv_url:
                    r = session.get(arxiv_url, timeout=30, verify=False)
                    if r.ok and 'application/pdf' in r.headers.get('content-type', '').lower():
                        if saveFile(pdf_dir, r.content, p, "arXiv"):
                            continue
                else:
                    print("    No matching paper found on arXiv.")
            except Exception as e:
                print(f"    arXiv check failed with an error: {e}")
        
        # Strategy 4: Anna's Archive (SciDB)
        if not p.downloaded and p.DOI:
            print("--> Checking Anna's Archive...")
            try:
                scidb_url = URLjoin(NetInfo.SciDB_URL, p.DOI)
                r = session.get(scidb_url, headers=NetInfo.HEADERS, timeout=30)
                if r.ok:
                    pdf_link = get_scidb_pdf_link(r.text)
                    if pdf_link:
                        pdf_response = session.get(pdf_link, timeout=45)
                        if pdf_response.ok and saveFile(pdf_dir, pdf_response.content, p, "Anna's Archive"):
                            continue
                    else:
                        print("    Could not find PDF link on Anna's Archive page.")
                else:
                    print(f"    Could not reach Anna's Archive for this paper (Status: {r.status_code}).")
            except Exception as e:
                print(f"    Anna's Archive check failed with an error: {e}")

        # Strategy 5: Sci-Hub
        if not p.downloaded and p.DOI:
            print("--> Checking Sci-Hub...")
            try:
                scihub_url = URLjoin(NetInfo.SciHub_URL, p.DOI)
                r = session.get(scihub_url, timeout=30, verify=False)
                if r.ok:
                    pdf_link = getSchiHubPDF(r.text)
                    if pdf_link:
                        pdf_response = session.get(pdf_link, timeout=45, verify=False)
                        if pdf_response.ok and saveFile(pdf_dir, pdf_response.content, p, "Sci-Hub"):
                            continue
                    else:
                        print("    Could not find PDF link on Sci-Hub page.")
                else:
                     print(f"    Could not reach Sci-Hub for this paper (Status: {r.status_code}).")
            except Exception as e:
                print(f"    Sci-Hub check failed with an error: {e}")
        
        if not p.downloaded:
            print("    Could not download paper from any available source.")