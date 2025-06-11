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
from unpywall import Unpywall  # CORRECTED: Added missing import
from .PapersFilters import similarStrings
from .HTMLparsers import getSchiHubPDF, SciHubUrls
from .NetInfo import NetInfo
from .Utils import URLjoin
from .GeminiDownloader import download_with_gemini_agent
import arxiv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Helper Functions (unchanged) ---
def setSciHubUrl(session):
    print("Searching for a sci-hub mirror...")
    try:
        r = session.get(NetInfo.SciHub_URLs_repo, headers=NetInfo.HEADERS, timeout=15)
        r.raise_for_status()
        links = SciHubUrls(r.text)
        for l in links:
            try:
                r = session.get(l, headers=NetInfo.HEADERS, timeout=10, verify=False)
                if r.status_code == 200:
                    NetInfo.SciHub_URL = l
                    print(f"Using Sci-Hub mirror: {l}")
                    return
            except requests.exceptions.RequestException:
                continue
    except requests.exceptions.RequestException as e:
        print(f"    Could not fetch Sci-Hub mirrors: {e}")
    print("\nNo working Sci-Hub instance found! Using default.")
    NetInfo.SciHub_URL = "https://sci-hub.se"


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

# --- Main Download Functions (Rewritten for Robustness) ---
def download_with_selenium_agent(url, final_file_path, paper_obj, source_name):
    print(f"    -> Trying browser fallback for {source_name}...")
    driver = None
    temp_dir = tempfile.mkdtemp()
    try:
        chrome_options = uc.ChromeOptions()
        prefs = {"download.default_directory": temp_dir, "plugins.always_open_pdf_externally": True}
        chrome_options.add_experimental_option("prefs", prefs)
        driver = uc.Chrome(options=chrome_options, headless=False, use_subprocess=True)
        driver.get(url)
        time.sleep(5)
        
        download_with_gemini_agent(driver, paper_obj)
        
        # Wait for download to complete
        for _ in range(45):
            files = [f for f in os.listdir(temp_dir) if f.endswith('.pdf') and not f.endswith('.crdownload')]
            if files:
                downloaded_file = path.join(temp_dir, files[0])
                # We need to move the file and then save it to the paper object
                shutil.move(downloaded_file, final_file_path)
                with open(final_file_path, 'rb') as f:
                    content = f.read()
                return saveFile(final_file_path, content, paper_obj, f"{source_name} (Gemini Agent)")
            time.sleep(1)
        print("    Download did not complete in time.")
        return False
    except Exception as e:
        print(f"    Browser fallback download failed. Reason: {e}")
        return False
    finally:
        if driver:
            driver.quit()
        if path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def downloadPapers(papers, dwnl_dir, num_limit, SciHub_URL=None, SciDB_URL=None, gemini_api_key=None):
    session = requests.Session()
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
                unpaywall_url = Unpaywall.get_doc_link(p.DOI)
                if unpaywall_url:
                    r = session.get(unpaywall_url, timeout=30, verify=False)
                    if r.ok and 'application/pdf' in r.headers.get('content-type', '').lower():
                        if saveFile(pdf_dir, r.content, p, "Unpaywall"):
                            continue
        except Exception as e:
            print(f"    Unpaywall failed. Reason: {type(e).__name__}")
        
        # Strategy 2: arXiv
        if not p.downloaded:
            print("--> Checking arXiv...")
            try:
                arxiv_url = get_arxiv_link(p.title, p)
                if arxiv_url:
                    r = session.get(arxiv_url, timeout=30, verify=False)
                    if r.ok and 'application/pdf' in r.headers.get('content-type', '').lower():
                        if saveFile(pdf_dir, r.content, p, "arXiv"):
                            continue
            except Exception as e:
                print(f"    arXiv failed. Reason: {type(e).__name__}")

        # Strategy 3: Publisher (via Gemini Agent)
        if not p.downloaded:
            publisher_url = f"https://doi.org/{p.DOI}" if p.DOI else p.scholar_link
            if publisher_url:
                if download_with_selenium_agent(publisher_url, pdf_dir, p, "Publisher"):
                    continue

        # Strategy 4: Sci-Hub
        if not p.downloaded and p.DOI:
            print("--> Checking Sci-Hub...")
            try:
                scihub_url = URLjoin(getattr(NetInfo, 'SciHub_URL', ''), p.DOI)
                r = session.get(scihub_url, timeout=30, verify=False)
                if r.ok:
                    pdf_link = getSchiHubPDF(r.text)
                    if pdf_link:
                        pdf_response = session.get(pdf_link, timeout=45, verify=False)
                        if pdf_response.ok and saveFile(pdf_dir, pdf_response.content, p, "Sci-Hub"):
                            continue
            except Exception as e:
                print(f"    Sci-Hub failed. Reason: {type(e).__name__}")