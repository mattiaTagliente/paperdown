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
from concurrent.futures import ThreadPoolExecutor, TimeoutError

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def download_from_scihub_with_browser(driver, temp_dir, scihub_url, paper_obj, final_file_path):
    """
    Uses a pre-initialized browser and a persistent temp folder to download from Sci-Hub.
    """
    print("    -> Using browser fallback for Sci-Hub...")
    try:
        files_before = set(os.listdir(temp_dir))
        
        driver.get(scihub_url)
        time.sleep(5) 
        
        pdf_link = getSchiHubPDF(driver.page_source)
        if not pdf_link:
            print("    -> Browser could not find PDF link on Sci-Hub page.")
            driver.get("about:blank")
            return False

        driver.get(pdf_link)
        print("    -> Waiting for download to complete...")
        time.sleep(10)

        files_after = set(os.listdir(temp_dir))
        new_files = files_after - files_before
        if not new_files:
            print("    ERROR: No new file was detected in the download directory.")
            driver.get("about:blank")
            return False

        downloaded_filename = new_files.pop()
        temp_file_path = os.path.join(temp_dir, downloaded_filename)

        shutil.move(temp_file_path, final_file_path)
        
        if path.exists(final_file_path) and os.path.getsize(final_file_path) > 1024:
            paper_obj.downloaded = True
            paper_obj.downloadedFrom = "Sci-Hub (Browser)"
            print("    Success: Downloaded from Sci-Hub (Browser).")
            return True

    except Exception as e:
        print(f"    ERROR: Browser download from Sci-Hub failed. Reason: {e}")
    
    finally:
        if driver:
            driver.get("about:blank")
            
    return False

def setSciHubUrl(session):
    print("Searching for a sci-hub mirror...")
    mirror_sources = ["https://sci-hub.ee/", "https://sci-hub.now.sh/", "https://sci-hub.st/", "https://sci-hub.se/"]
    for source_url in mirror_sources:
        try:
            r = session.get(source_url, headers=NetInfo.HEADERS, timeout=10, verify=False)
            if r.status_code == 200 and "Sci-Hub" in r.text:
                NetInfo.SciHub_URL = source_url
                print(f"Found working Sci-Hub mirror (for direct requests): {source_url}")
                return
        except requests.exceptions.RequestException:
            continue
    print("\nNo working mirror for direct requests found. Will rely on browser-based download.")
    NetInfo.SciHub_URL = "https://sci-hub.se/"

def getSaveDir(folder, fname):
    dir_ = path.join(folder, fname)
    n = 1
    while path.exists(dir_):
        n += 1
        dir_ = path.join(folder, f"({n}){fname}")
    return dir_

def _execute_arxiv_search(title):
    try:
        query = f'ti:"{title}"'
        print(f"    -> Searching arXiv with query: {query}")
        search = arxiv.Search(query=query, max_results=1)
        result = next(search.results(), None)
        if result and similarStrings(result.title.lower(), title.lower()) > 0.8:
            print(f"    -> Found matching paper on arXiv: {result.title}")
            return result.pdf_url
    except Exception as e:
        print(f"    arXiv search raised an exception: {e}")
    return None

def get_arxiv_link(title, paper_obj):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_execute_arxiv_search, title)
        try:
            return future.result(timeout=15)
        except TimeoutError:
            print("    arXiv search timed out after 15 seconds.")
            return None
        except Exception as e:
            print(f"    arXiv search failed: {e}")
            return None

def saveFile(file_name, content, paper, dwn_source):
    try:
        with open(file_name, 'wb') as f: f.write(content)
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

# --- FINAL VERSION ---
def downloadPapers(papers, dwnl_dir, num_limit, SciHub_URL=None, SciDB_URL=None, gemini_api_key=None):
    session = requests.Session()
    session.headers.update(NetInfo.HEADERS)
    NetInfo.gemini_api_key = gemini_api_key
    if not getattr(NetInfo, 'SciHub_URL', None):
        setSciHubUrl(session)

    browser_driver = None
    temp_download_dir = None
    
    try:
        for i, p in enumerate(papers):
            if (num_limit is not None and i >= num_limit) or p.downloaded:
                continue

            print(f"\n[{i+1}/{len(papers)}] Processing: {p.title[:60]}...")
            pdf_dir = getSaveDir(dwnl_dir, p.getFileName())

            # Strategy 1: Unpaywall
            if not p.downloaded:
                print("--> Checking Unpaywall...")
                try:
                    if p.DOI:
                        unpaywall_url = Unpywall.get_doc_link(p.DOI)
                        if unpaywall_url:
                            print(f"    -> Unpaywall found an OA link: {unpaywall_url}")
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
                arxiv_url = get_arxiv_link(p.title, p)
                if arxiv_url:
                    try:
                        r = session.get(arxiv_url, timeout=30, verify=False)
                        if r.ok and 'application/pdf' in r.headers.get('content-type', '').lower():
                            if saveFile(pdf_dir, r.content, p, "arXiv"):
                                continue
                    except Exception as e:
                        print(f"    arXiv download failed with an error: {e}")
                else:
                    print("    No matching paper found on arXiv.")
            
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
                
                if browser_driver is None:
                    print("    -> Initializing browser for secure downloads...")
                    temp_download_dir = tempfile.mkdtemp()
                    options = uc.ChromeOptions()
                    options.add_argument('--headless')
                    prefs = {"download.default_directory": temp_download_dir}
                    options.add_experimental_option("prefs", prefs)
                    browser_driver = uc.Chrome(options=options)

                scihub_url_to_try = URLjoin(NetInfo.SciHub_URL, p.DOI)
                if download_from_scihub_with_browser(browser_driver, temp_download_dir, scihub_url_to_try, p, pdf_dir):
                    continue

            if not p.downloaded:
                print("    Could not download paper from any available source.")

    finally:
        if browser_driver:
            print("\nShutting down browser instance...")
            browser_driver.quit()
            # Setting to None prevents the destructor from trying to quit a second time
            browser_driver = None 
        if temp_download_dir and os.path.exists(temp_download_dir):
            shutil.rmtree(temp_download_dir)