# PyPaperBot/Downloader.py
from os import path
import os
import requests
import urllib3
import time
import random
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options

# --- PyPaperBot/Unpaywall Imports ---
from unpywall import Unpywall
import arxiv
from .PapersFilters import similarStrings
from .HTMLparsers import getSchiHubPDF, SciHubUrls
from .NetInfo import NetInfo
from .Utils import URLjoin

# Suppress the InsecureRequestWarning from using verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def setSciHubUrl(session):
    """
    Finds a working Sci-Hub mirror.
    """
    print("Searching for a sci-hub mirror...")
    try:
        r = session.get(NetInfo.SciHub_URLs_repo, headers=NetInfo.HEADERS, timeout=15)
        r.raise_for_status()
        links = SciHubUrls(r.text)

        for l in links:
            try:
                print(f"Trying with {l}...")
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


def saveFile(file_name, content, paper, dwn_source):
    """
    Saves content to a file.
    """
    try:
        print(f"    Attempting to save file to: {file_name}")
        with open(file_name, 'wb') as f:
            f.write(content)
        
        if path.exists(file_name) and os.path.getsize(file_name) > 0:
            paper.downloaded = True
            paper.downloadedFrom = dwn_source
            print(f"    Success: Downloaded from {dwn_source}.")
            return True
        else:
            print("    ERROR: File write failed silently (file is empty).")
            return False
            
    except (IOError, PermissionError) as e:
        print(f"    ERROR: Could not save file. Check permissions or path.\n    Reason: {e}")
        return False

def find_pdf_link_in_html(html_content, base_url):
    """
    Parses HTML content to find a link to a PDF file.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    meta_tag = soup.find('meta', {'name': 'citation_pdf_url'})
    if meta_tag and meta_tag.get('content'):
        return urljoin(base_url, meta_tag.get('content'))
    
    for link in soup.find_all('a', href=lambda href: href and (href.lower().endswith('.pdf') or 'pdf' in href.lower())):
        return urljoin(base_url, link.get('href'))
    return None

def download_with_selenium(url, file_path, paper_obj, source_name):
    """
    Fallback downloader using a headless browser for sites with anti-bot measures or complex JavaScript.
    """
    print(f"    Trying browser fallback for {source_name}...")
    driver = None
    try:
        options = Options()
        options.add_argument('--headless')
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = uc.Chrome(options=options)
        
        driver.get(url)
        time.sleep(10) # Wait for page load and JS execution

        pdf_content = requests.get(driver.current_url, headers=NetInfo.HEADERS, verify=False, timeout=45).content
        
        if saveFile(file_path, pdf_content, paper_obj, f"{source_name} (Browser Fallback)"):
            return True

    except Exception as e:
        print(f"    Browser fallback download failed. Reason: {e}")
    finally:
        if driver:
            driver.quit()
    return False


def downloadPapers(papers, dwnl_dir, num_limit, SciHub_URL=None, SciDB_URL=None):
    """
    Main download function with expanded Selenium fallback and a final DOI link check.
    """
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=3)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    if SciHub_URL:
        NetInfo.SciHub_URL = SciHub_URL
    else:
        setSciHubUrl(session)

    if SciDB_URL:
        NetInfo.SciDB_URL = SciDB_URL

    num_downloaded = 0
    for i, p in enumerate(papers):
        if num_limit is not None and num_downloaded >= num_limit:
            break
            
        if not p.canBeDownloaded():
            continue

        print(f"\n[{i+1}/{len(papers)}] Processing: {p.title[:60]}...")
        pdf_dir = getSaveDir(dwnl_dir, p.getFileName())

        download_sources = [
            ("Unpaywall", p.DOI, lambda doi: Unpywall.get_doc_link(doi)),
            ("arXiv", p.title, lambda title: get_arxiv_link(title, p)),
            ("SciDB", p.DOI, lambda doi: URLjoin(NetInfo.SciDB_URL, doi) if doi else None),
            ("SciHub", p.DOI, lambda doi: URLjoin(NetInfo.SciHub_URL, doi) if doi else None),
            # **NEW FINAL FALLBACK**
            ("DOI Link", p.DOI, lambda doi: f"https://doi.org/{doi}" if doi else None)
        ]

        for source_name, identifier, url_func in download_sources:
            if p.downloaded: break
            if not identifier: continue

            print(f"--> Checking {source_name}...")
            verify_ssl = source_name not in ["SciDB", "SciHub"]
            
            try:
                url = url_func(identifier)
                if not url:
                    print(f"    No link found on {source_name}.")
                    continue
                
                print(f"    Found URL: {url}")
                r = session.get(url, headers=NetInfo.HEADERS, timeout=30, verify=verify_ssl)
                
                if r.status_code == 403:
                    if download_with_selenium(url, pdf_dir, p, source_name):
                        num_downloaded += 1
                    continue

                r.raise_for_status()
                content_type = r.headers.get('content-type', '').lower()
                
                if 'application/pdf' in content_type or 'application/octet-stream' in content_type:
                    if saveFile(pdf_dir, r.content, p, source_name):
                        num_downloaded += 1
                
                elif 'text/html' in content_type:
                    pdf_link = getSchiHubPDF(r.text) or find_pdf_link_in_html(r.text, r.url)
                    if pdf_link:
                        print(f"    Found embedded PDF link: {pdf_link}")
                        pdf_response = session.get(pdf_link, headers=NetInfo.HEADERS, timeout=30, verify=verify_ssl)
                        pdf_response.raise_for_status()
                        if saveFile(pdf_dir, pdf_response.content, p, f"{source_name} (scraped)"):
                            num_downloaded += 1
                    else:
                        print("    HTML page found, but no direct PDF link. Trying browser fallback...")
                        if download_with_selenium(url, pdf_dir, p, source_name):
                            num_downloaded += 1
                
                else:
                    if saveFile(pdf_dir, r.content, p, source_name):
                        num_downloaded += 1

            except requests.exceptions.RequestException as e:
                print(f"    Download from {source_name} failed. Reason: {e}")
            except Exception as e:
                print(f"    An unexpected error occurred with {source_name}. Reason: {e}")


def get_arxiv_link(title, paper_obj):
    """
    Helper function to search arXiv and return a PDF link.
    """
    try:
        query = f'ti:"{title}"'
        if paper_obj.authors:
            main_author = paper_obj.authors.split(';')[0].split(',')[0].strip()
            query += f' AND au:"{main_author}"'
        
        search = arxiv.Search(query=query, max_results=1)
        result = next(search.results(), None)
        
        if result and similarStrings(result.title.lower(), title.lower()) > 0.8:
            return result.pdf_url
    except Exception as e:
        print(f"    arXiv search failed: {e}")
    return None