# PyPaperBot/Scholar.py
import time
import requests
import functools
import undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options
from .HTMLparsers import schoolarParser
from .Crossref import getPapersInfo
from .NetInfo import NetInfo
from .Paper import Paper


def waithIPchange():
    while True:
        inp = input('You have been blocked, try changing your IP or using a VPN. '
                    'Press Enter to continue downloading, or type "exit" to stop and exit....')
        if inp.strip().lower() == "exit":
            return False
        elif not inp.strip():
            print("Wait 30 seconds...")
            time.sleep(30)
            return True


def scholar_requests(scholar_pages, url, restrict, chrome_version, scholar_results=10, fetch_metadata=True):
    javascript_error = "Sorry, we can't verify that you're not a robot when JavaScript is turned off"
    to_download = []
    driver = None
    for i in scholar_pages:
        while True:
            res_url = url % (scholar_results * (i - 1))
            if chrome_version is not None:
                if driver is None:
                    print("Using Selenium driver")
                    options = Options()
                    options.add_argument('--headless')
                    driver = uc.Chrome(headless=True, use_subprocess=False, version_main=chrome_version)
                driver.get(res_url)
                html = driver.page_source
            else:
                html = requests.get(res_url, headers=NetInfo.HEADERS)
                html = html.text

            if javascript_error in html:
                is_continue = waithIPchange()
                if not is_continue:
                    return to_download
            else:
                break

        papers = schoolarParser(html)
        if len(papers) > scholar_results:
            papers = papers[0:scholar_results]

        print("\nGoogle Scholar page {} : {} papers found".format(i, len(papers)))

        if len(papers) > 0:
            if fetch_metadata:
                # The old, slow path: get Crossref info for all results immediately
                papersInfo = getPapersInfo(papers, url, restrict, scholar_results)
                info_valids = functools.reduce(lambda a, b: a + 1 if b.DOI is not None else a, papersInfo, 0)
                print("Papers found on Crossref: {}/{}\n".format(info_valids, len(papers)))
                to_download.append(papersInfo)
            else:
                # The new, fast path: just create basic Paper objects without Crossref info
                paper_objects = [
                    Paper(p['title'], p['link'], url, p['cites'], p['link_pdf'], p['year'], p['authors'])
                    for p in papers
                ]
                to_download.append(paper_objects)
        else:
            print("Paper not found...")

    return to_download


def parseSkipList(skip_words):
    skip_list = skip_words.split(",")
    print("Skipping results containing {}".format(skip_list))
    output_param = ""
    for skip_word in skip_list:
        skip_word = skip_word.strip()
        if " " in skip_word:
            output_param += '+-"' + skip_word + '"'
        else:
            output_param += '+-' + skip_word
    return output_param


def ScholarPapersInfo(query, scholar_pages, restrict=None, min_date=None, max_date=None, scholar_results=10, chrome_version=None, cites=None, skip_words=None, fetch_metadata=True):
    """
    Main function to get paper info from Google Scholar.
    Includes 'fetch_metadata' flag to control expensive Crossref lookups.
    """
    url = r"https://scholar.google.com/scholar?hl=en&as_vis=1&as_sdt=1,5&start=%d"
    if query:
        if len(query) > 7 and (query.startswith("http://") or query.startswith("https://")):
            url = query
        else:
            url += f"&q={query}"
        if skip_words:
            url += parseSkipList(skip_words)
    if cites:
        url += f"&cites={cites}"
    if min_date:
        url += f"&as_ylo={min_date}"
    if max_date:
        url += f"&as_yhi={max_date}"

    to_download = scholar_requests(scholar_pages, url, restrict, chrome_version, scholar_results, fetch_metadata)

    return [item for sublist in to_download for item in sublist]