# PyPaperBot/RelevanceSearch.py
import os
import re
from .Scholar import ScholarPapersInfo
from .Crossref import getPapersInfo
from .Downloader import downloadPapers
from .Paper import generate_custom_bibtex, generate_citekeys
from .MetadataFetcher import enrich_paper_with_abstract

def find_relevant_papers(
    topic,
    start_year,
    end_year,
    base_dwn_dir,
    num_reviews=3,
    num_non_reviews=6,
    s2_api_key=None,
    gemini_api_key=None,
):
    """
    Finds, enriches, and downloads the most relevant papers for a given topic.
    """
    print("--- Starting Relevance Search ---")
    print(f"Topic: {topic}, Date Range: {start_year}-{end_year}")

    # --- Phase 1: Find review papers ---
    print("\n[Phase 1/4] Searching for review papers...")
    review_query = f"{topic} review"
    top_reviews = ScholarPapersInfo(review_query, range(1, 2), min_date=start_year, max_date=end_year, fetch_metadata=False)[:num_reviews]
    print(f"Selected top {len(top_reviews)} review papers.")

    # --- Phase 2: Find non-review papers ---
    print("\n[Phase 2/4] Searching for non-review papers...")
    all_papers_query = topic
    pages_to_search = 1 + ((num_non_reviews + len(top_reviews)) // 10)
    all_results = ScholarPapersInfo(all_papers_query, range(1, pages_to_search + 1), min_date=start_year, max_date=end_year, fetch_metadata=False)
    review_titles = {p.title for p in top_reviews}
    top_non_reviews = [p for p in all_results if p.title not in review_titles][:num_non_reviews]
    print(f"Selected top {len(top_non_reviews)} non-review papers.")

    final_paper_list = top_reviews + top_non_reviews
    if not final_paper_list:
        print("No papers found.")
        return

    # --- Phase 3: Fetch full metadata (Authors, DOI, etc.) ---
    print("\n[Phase 3/4] Fetching full metadata...")
    final_paper_list = getPapersInfo(final_paper_list, s2_api_key)

    # --- Phase 4: Generate Citekeys and Download ---
    print("\n[Phase 4/4] Generating citekeys and downloading...")
    final_paper_list = generate_citekeys(final_paper_list)

    # Add verbose logging for assigned citekeys
    print("\n--- Final Citekeys Assigned ---")
    for p in final_paper_list:
        print(f"  - {p.citekey:<25} | {p.title}")
    print("-----------------------------\n")

    folder_name = re.sub(r'[^\w\-_\. ]', '_', f"{topic.replace(' ', '_')}_{start_year}-{end_year}")
    results_dir = os.path.join(base_dwn_dir, folder_name)
    os.makedirs(results_dir, exist_ok=True)
    print(f"Results will be saved in: {results_dir}")

    bibtex_path = os.path.join(results_dir, "references.bib")
    generate_custom_bibtex(final_paper_list, bibtex_path)

    downloadPapers(
        final_paper_list,
        results_dir,
        num_limit=len(final_paper_list),
        gemini_api_key=gemini_api_key,
    )