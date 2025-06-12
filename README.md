# Advanced Paper Downloader

This is a significantly enhanced version of the original PyPaperBot, designed to be a powerful, all-in-one tool for academic research. It provides a user-friendly graphical interface to find, download, and manage research papers and their bibliographic information.

This version was developed with a focus on efficiency, reliability, and providing complete metadata for citation management.

## Core Features

-   **Dual Search Modes:**
    -   **Standard Search:** Download papers directly using a Google Scholar query or a specific DOI.
    -   **Relevance Search:** Automatically find the most relevant review and non-review papers for a given topic and date range, based on Google Scholar's rankings.

-   **Robust, Multi-Source Downloading:**
    -   The downloader intelligently attempts to find a PDF from the best available sources in the following order: Unpaywall, direct DOI link, arXiv, Anna's Archive, and Sci-Hub.
    -   For sources protected by strong anti-bot measures (like Sci-Hub), the tool automatically uses a **headless browser instance** to simulate human interaction and secure the download.

-   **Complete Bibliographic Data:**
    -   Automatically generates a `.bib` file for all collected papers.
    -   Creates custom, disambiguated citation keys (e.g., `[SurnameYEARThea]`) for easy reference.
    -   Enriches BibTeX entries by fetching missing abstracts from the **Semantic Scholar API**.

-   **Intelligent Caching:**
    -   All fetched metadata is cached locally in the `cache/` directory to speed up subsequent runs and reduce network requests.
    -   The cache uses the robust, generated `citekey` as its primary identifier and is backward-compatible with older cache formats.

-   **User-Friendly Interface:**
    -   A graphical interface built with Tkinter for easy operation.
    -   Remembers your selected download folder between sessions.
    -   Provides a real-time log of the script's actions.

## Requirements

-   Python 3.8+
-   Git
-   A handful of Python packages, listed in `requirements.txt`.
-   An email address for the Unpaywall API, and optional API keys for Semantic Scholar and Gemini.

## Setup and Installation

1.  **Clone the Repository:**
    ```bash
    git clone <your-repository-url>
    cd <repository-name>
    ```

2.  **Create a Virtual Environment:**
    ```bash
    # On Windows
    python -m venv venv
    venv\Scripts\activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Create Credentials File:**
    In the root project folder, create a file named `credentials.txt`. This file **must** have the `[credentials]` header. Add your email and optional API keys here.
    ```ini
    [credentials]
    email = your_email@provider.com
    s2_api_key = your_semantic_scholar_api_key_here
    gemini_api_key = your_gemini_api_key_here
    ```

## How to Use

1.  **Run the Application:**
    With your virtual environment activated, run the following command in your terminal:
    ```bash
    python gui.py
    ```

2.  **Configure Download Folder:**
    The first time you run the app, it will prompt you to select a folder where all downloaded papers and BibTeX files will be saved. The app will remember this location for future sessions.

3.  **Select a Search Mode:**
    -   **Standard Search:** Enter a search query or a single DOI to download specific papers.
    -   **Find Relevant Papers:** Enter a research topic, a date range, and the number of review/non-review papers you want.

4.  **Click Search:**
    The output log will show the script's progress in real-time.

## Command-Line Interface (CLI)

For advanced users and automation, the original command-line interface is still available. You can access it by running the `PyPaperBot` module directly. For a full list of commands and options, use the help flag:
```bash
python -m PyPaperBot.__main__ --help