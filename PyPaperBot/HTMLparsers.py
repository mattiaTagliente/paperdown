# PyPaperBot/HTMLparsers.py
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin


def schoolarParser(html):
    result = []
    soup = BeautifulSoup(html, "html.parser")
    for element in soup.findAll("div", class_="gs_r gs_or gs_scl"):
        if not isBook(element):
            title = None
            link = None
            link_pdf = None
            cites = None
            year = None
            authors = None
            for h3 in element.findAll("h3", class_="gs_rt"):
                found = False
                for a in h3.findAll("a"):
                    if not found:
                        title = a.text
                        link = a.get("href")
                        found = True
            for a in element.findAll("a"):
                if "Cited by" in a.text:
                    cites = int(a.text[8:])
                if "[PDF]" in a.text:
                    link_pdf = a.get("href")
            for div in element.findAll("div", class_="gs_a"):
                try:
                    authors, source_and_year, source = div.text.replace('\u00A0', ' ').split(" - ")
                except ValueError:
                    continue

                # Keep the author string from scholar, even if truncated.
                # It will be overwritten by the authoritative one from Crossref later.
                authors = authors.replace(', ', ';').replace('\u2026', '').strip()

                try:
                    year = int(source_and_year[-4:])
                except ValueError:
                    continue
                if not (1000 <= year <= 3000):
                    year = None
                else:
                    year = str(year)
            if title is not None:
                result.append({
                    'title': title,
                    'link': link,
                    'cites': cites,
                    'link_pdf': link_pdf,
                    'year': year,
                    'authors': authors})
    return result


def isBook(tag):
    result = False
    for span in tag.findAll("span", class_="gs_ct2"):
        if span.text == "[B]":
            result = True
    return result


def getSchiHubPDF(html):
    soup = BeautifulSoup(html, "html.parser")
    iframe = soup.find(id='pdf')
    if iframe:
        src = iframe.get("src")
        if src and not src.startswith('http'):
            return "https:" + src
        return src
    return None

def get_scidb_pdf_link(html):
    soup = BeautifulSoup(html, "html.parser")
    download_link = soup.find("a", href=re.compile(r"downloads.annas-archive.org"))
    if download_link:
        return download_link.get("href")
    return None


def SciHubUrls(html):
    result = []
    soup = BeautifulSoup(html, "html.parser")
    for ul in soup.findAll("ul"):
        for a in ul.findAll("a"):
            link = a.get("href")
            if link and (link.startswith("https://sci-hub.") or link.startswith("http://sci-hub.")):
                result.append(link)
    return result

def scrape_page_for_pdf_link(html, page_url):
    """
    Performs a best-effort scrape of an HTML page to find a link to a PDF.
    """
    soup = BeautifulSoup(html, "html.parser")
    # Look for <a> tags with hrefs ending in .pdf, or containing 'download' and 'pdf'
    for a in soup.find_all('a', href=True):
        href = a['href'].lower()
        text = a.text.lower()
        if href.endswith('.pdf'):
            # Construct absolute URL if necessary
            return urljoin(page_url, a['href'])
        if ('download' in text or 'pdf' in text) and ('.pdf' in href or 'content/pdf' in href):
            return urljoin(page_url, a['href'])
    print("    -> Scraper could not find a PDF link on the page.")
    return None