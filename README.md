# Advanced Paper Downloader

This is a significantly enhanced version of the original PyPaperBot, designed to be a powerful, all-in-one tool for academic research. It provides a user-friendly graphical interface to find, download, and manage research papers and their bibliographic information.

This version was developed with a focus on efficiency, reliability, and providing complete metadata for citation management.

![GUI Screenshot](image_c99130.png)

## Core Features

- **Dual Search Modes:**
    - **Standard Search:** Download papers directly using a Google Scholar query or a specific DOI.
    - **Relevance Search:** Automatically find the most relevant review and non-review papers for a given topic and date range, based on Google Scholar's rankings.
- **Robust Downloading:**
    - Prioritizes legal, open-access sources via **Unpaywall**.
    - Intelligently scrapes publisher landing pages if a direct PDF link is not available.
    - Searches **arXiv** for pre-prints.
    - Falls back to other resources like **SciDB** and **Sci-Hub** if primary methods fail.
- **Complete Bibliographic Data:**
    - Automatically generates a `.bib` file for all collected papers.
    - Creates custom, disambiguated citation keys (e.g., `[SurnameYEARThea]`) for easy reference.
    - Enriches BibTeX entries by fetching missing abstracts from the **Semantic Scholar API**.
- **User-Friendly Interface:**
    - A graphical interface built with Tkinter for easy operation on Windows.
    - Remembers your selected download folder between sessions.
    - Provides a real-time log of the script's actions.

## Requirements

- Python 3.8+
- Git
- A handful of Python packages, listed in `requirements.txt`.
- An email address for the Unpaywall API and an optional API key for Semantic Scholar.

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
    pip install unpywall arxiv
    ```

4.  **Create Credentials File:**
    In the root project folder, create a file named `credentials.txt`. This file **must** have the `[credentials]` header. Add your email and optional Semantic Scholar API key here. The script will not work without a valid email.
    ```ini
    [credentials]
    email = your_email@provider.com
    s2_api_key = your_semantic_scholar_api_key_here
    ```

## How to Use

1.  **Run the Application:**
    With your virtual environment activated, run the following command in your terminal:
    ```bash
    python gui.py
    ```

2.  **Configure Download Folder:**
    The first time you run the app, it will prompt you to select a folder where all downloaded papers and BibTeX files will be saved. The app will remember this location for future sessions. You can change it anytime using the "Change..." button.

3.  **Select a Search Mode:**
    - **Standard Search:** Enter a search query or a single DOI to download specific papers.
    - **Find Relevant Papers:** Enter a research topic, a date range, and the number of review/non-review papers you want. The script will find the most relevant ones, download them, and generate a corresponding BibTeX file.

4.  **Click Search:**
    The output log will show the script's progress in real-time. Once finished, a popup will notify you, and you can find all the files in the subfolder created within your chosen download directory.

## Acknowledgements
This project is a heavily modified fork of the original [PyPaperBot by ferru97](https://github.com/ferru97/PyPaperBot). It builds upon its solid foundation by adding new features, a graphical interface, and a more robust, multi-source download strategy.