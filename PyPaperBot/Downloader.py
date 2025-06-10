# PyPaperBot/Downloader.py
from os import path
import os
import requests
import time
import random
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# --- PyPaperBot/Unpaywall Imports ---
from unpywall import Unpywall
import arxiv
from .PapersFilters import similarStrings
from .HTMLparsers import getSchiHubPDF, SciHubUrls
from .NetInfo import NetInfo
from .Utils import URLjoin


def setSciHubUrl():
    print("Searching for a sci-hub mirror")
    r = requests.get(NetInfo.SciHub_URLs_repo, headers=NetInfo.HEADERS)
    links = SciHubUrls(r.text)

    for l in links:
        try:
            print(f"Trying with {l}...")
            r = requests.get(l, headers=NetInfo.HEADERS)
            if r.status_code == 200:
                NetInfo.SciHub_URL = l
                break
        except:
            pass
    else:
        print(
            "\nNo working Sci-Hub instance found!\nIf in your country Sci-Hub is not available consider using a VPN or a proxy\nYou can use a specific mirror with the --scihub-mirror argument")
        NetInfo.SciHub_URL = "https://sci-hub.st"


def getSaveDir(folder, fname):
    dir_ = path.join(folder, fname)
    n = 1
    while path.exists(dir_):
        n += 1
        dir_ = path.join(folder, f"({n}){fname}")
    return dir_


def saveFile(file_name, content, paper, dwn_source):
    """
    Saves content to a file and provides explicit error handling.
    Returns True on success, False on failure.
    """
    try:
        print(f"    Attempting to save file to: {file_name}")
        with open(file_name, 'wb') as f:
            f.write(content)
        
        # After writing, verify that the file actually exists and has content.
        if path.exists(file_name) and os.path.getsize(file_name) > 0:
            paper.downloaded = True
            paper.downloadedFrom = dwn_source
            return True
        else:
            print("    ERROR: File write operation failed silently. The file was not created or is empty.")
            return False
            
    except (IOError, PermissionError) as e:
        print(f"    ERROR: Could not save file. Please check permissions or path.\n    Reason: {e}")
        return False

def find_pdf_link_in_html(html_content, base_url):
    """
    Parses HTML content to find a link to a PDF file, now checks meta tags.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    # Strategy 1: Look for <meta name="citation_pdf_url" ...>
    meta_tag = soup.find('meta', {'name': 'citation_pdf_url'})
    if meta_tag and meta_tag.get('content'):
        return urljoin(base_url, meta_tag.get('content'))
    
    # Strategy 2: Fallback to finding <a> tags ending in .pdf
    for link in soup.find_all('a', href=lambda href: href and href.lower().endswith('.pdf')):
        return urljoin(base_url, link.get('href'))
    return None


def downloadPapers(papers, dwnl_dir, num_limit, SciHub_URL=None, SciDB_URL=None):
    """
    Enhanced download function that can scrape landing pages for PDF links.
    """
    if SciHub_URL:
        NetInfo.SciHub_URL = SciHub_URL
    if SciDB_URL:
        NetInfo.SciDB_URL = SciDB_URL

    num_downloaded = 0
    paper_number = 1

    for p in papers:
        if p.canBeDownloaded() and (num_limit is None or num_downloaded < num_limit):
            print(f"\nProcessing paper {paper_number} of {len(papers)} -> {p.title}")
            paper_number += 1
            pdf_dir = getSaveDir(dwnl_dir, p.getFileName())

            # --- ATTEMPT 1: Unpaywall (with HTML parsing fallback) ---
            if p.DOI:
                print("--> Checking Unpaywall...")
                try:
                    oa_url = Unpywall.get_doc_link(p.DOI)
                    print(f"    Unpaywall returned URL: {oa_url}") # Debugging log
                    if oa_url:
                        r = requests.get(oa_url, headers=NetInfo.HEADERS, timeout=20)
                        content_type = r.headers.get('content-type', '').lower()

                        # Case 1: The link is a direct PDF
                        if 'application/pdf' in content_type:
                            if saveFile(pdf_dir, r.content, p, "Unpaywall"):
                                print("    Success: Downloaded directly.")
                                num_downloaded += 1
                                continue
                        
                        # Case 2: The link is an HTML landing page
                        elif 'text/html' in content_type:
                            print("    Link is a landing page. Searching for PDF in HTML...")
                            html_pdf_link = find_pdf_link_in_html(r.text, r.url)
                            if html_pdf_link:
                                print(f"    Found potential PDF link on page: {html_pdf_link}")
                                pdf_response = requests.get(html_pdf_link, headers=NetInfo.HEADERS, timeout=30)
                                if 'application/pdf' in pdf_response.headers.get('content-type', '').lower():
                                    if saveFile(pdf_dir, pdf_response.content, p, "Unpaywall (scraped)"):
                                        print("    Success: Downloaded from scraped link.")
                                        num_downloaded += 1
                                        continue
                                else:
                                    print("    Warning: Scraped link was not a direct PDF.")
                            else:
                                print("    Could not find a direct .pdf link on the landing page.")
                    else:
                        print("    No open-access link found on Unpaywall.")
                except Exception as e:
                     print(f"    Unpaywall check failed: {e}")

            # --- ATTEMPT 2: arXiv ---
            print("--> Checking arXiv...")
            try:
                search = arxiv.Search(query=f'"{p.title}"', max_results=1)
                paper_result = next(search.results(), None)
                if paper_result and similarStrings(paper_result.title.lower(), p.title.lower()) > 0.8:
                    try:
                        print(f"    Attempting to save file to: {pdf_dir}")
                        paper_result.download_pdf(dirpath=dwnl_dir, filename=p.getFileName())
                        p.downloaded = True
                        p.downloadedFrom = "arXiv"
                        print("    Success: Downloaded from arXiv.")
                        num_downloaded += 1
                        continue
                    except Exception as e:
                        print(f"    ERROR: Could not save file from arXiv. Reason: {e}")
                else:
                    print("    No relevant paper found on arXiv.")
            except Exception as e:
                print(f"    arXiv search failed: {e}")

            # --- ATTEMPT 3: Fallback to PyPaperBot's original methods (SciDB/SciHub) ---
            print("--> Falling back to SciDB/SciHub...")
            if NetInfo.SciHub_URL is None: setSciHubUrl()
            if NetInfo.SciHub_URL: print(f"    Using Sci-Hub mirror: {NetInfo.SciHub_URL}")

            failed = 0
            url = ""
            while not p.downloaded and failed != 5:
                try:
                    dwn_source = 1; source_name = "SciDB"
                    if failed == 0 and p.DOI: url = URLjoin(NetInfo.SciDB_URL, p.DOI)
                    if failed == 1 and p.DOI: url = URLjoin(NetInfo.SciHub_URL, p.DOI); source_name = "SciHub"; dwn_source = 2
                    if failed == 2 and p.scholar_link: url = URLjoin(NetInfo.SciHub_URL, p.scholar_link); source_name = "SciHub (from Scholar)"
                    if failed == 3 and p.scholar_link and p.scholar_link.endswith(".pdf"): url = p.scholar_link; source_name = "Scholar (direct PDF)"; dwn_source = 3
                    if failed == 4 and p.pdf_link: url = p.pdf_link; source_name = "Scholar (direct PDF)"; dwn_source = 3

                    if url:
                        print(f"    Trying source: {source_name}")
                        r = requests.get(url, headers=NetInfo.HEADERS, timeout=20)
                        ct = r.headers.get('content-type', '')
                        if ('application/pdf' not in ct and "application/octet-stream" not in ct) and (dwn_source in [1, 2]):
                            time.sleep(random.randint(1, 4))
                            pdf_link = getSchiHubPDF(r.text)
                            if pdf_link:
                                r = requests.get(pdf_link, headers=NetInfo.HEADERS)
                                ct = r.headers.get('content-type', '')

                        if 'application/pdf' in ct or "application/octet-stream" in ct:
                            if saveFile(pdf_dir, r.content, p, dwn_source): num_downloaded += 1
                except Exception as e:
                    print(f"    Download from {source_name} failed: {e}")
                failed += 1