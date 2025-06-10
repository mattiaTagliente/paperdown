# PyPaperBot/Paper.py
import bibtexparser
import re
import pandas as pd
import urllib.parse

class Paper:
    def __init__(self,title=None, scholar_link=None, scholar_page=None, cites=None, link_pdf=None, year=None, authors=None):        
        self.title = title
        self.scholar_page = scholar_page
        self.scholar_link = scholar_link
        self.pdf_link = link_pdf
        self.year = year
        self.authors = authors

        self.jurnal = None
        self.cites_num = cites
        self.bibtex = None
        self.DOI = None
        self.citekey = None # For custom citation key

        self.downloaded = False
        self.downloadedFrom = 0  # 1-SciHub 2-scholar
        
        self.use_doi_as_filename = False

    def getFileName(self):
        try:
            if self.use_doi_as_filename and self.DOI:
                return urllib.parse.quote(self.DOI, safe='') + ".pdf"
            else:
                return re.sub(r'[^\w\-_. ]', '_', self.title) + ".pdf"
        except:
            return "none.pdf"

    def setBibtex(self, bibtex):
        try:
            parser = bibtexparser.bparser.BibTexParser(common_strings=True)
            x = bibtexparser.loads(bibtex, parser=parser).entries
            if not x: return
            
            self.bibtex = bibtex
            entry = x[0]

            if "year" in entry: self.year = entry["year"]
            if 'author' in entry: self.authors = entry["author"]
            self.jurnal = entry.get("journal", entry.get("publisher", "")).replace("\\", "")
        except Exception as e:
            print(f"    Warning: Could not parse bibtex for '{self.title}'. Reason: {e}")
            pass

    def canBeDownloaded(self):
        return self.DOI is not None or self.scholar_link is not None

    @staticmethod
    def generateReport(papers, path):
        columns = ["Name", "Scholar Link", "DOI", "Bibtex", "PDF Name", "Year", "Journal", "Downloaded", "Downloaded from", "Authors", "Cite Key"]
        data = []
        for p in papers:
            pdf_name = p.getFileName() if p.downloaded else ""
            bibtex_found = p.bibtex is not None
            dwn_from = ""
            if isinstance(p.downloadedFrom, str):
                dwn_from = p.downloadedFrom
            elif p.downloadedFrom == 1: dwn_from = "SciDB"
            elif p.downloadedFrom == 2: dwn_from = "SciHub"
            elif p.downloadedFrom == 3: dwn_from = "Scholar"
            data.append({
                "Name": p.title, "Scholar Link": p.scholar_link, "DOI": p.DOI,
                "Bibtex": bibtex_found, "PDF Name": pdf_name, "Year": p.year,
                "Journal": p.jurnal, "Downloaded": p.downloaded, "Downloaded from": dwn_from,
                "Authors": p.authors, "Cite Key": p.citekey
            })
        df = pd.DataFrame(data, columns=columns)
        df.to_csv(path, index=False, encoding='utf-8')

# --- New Functionality for Custom BibTeX ---
def generate_citekey(paper, existing_keys):
    """Generates a custom BibTeX key in the format [SurnameYEARTitn]."""
    if not paper.authors: paper.authors = "Unknown"
    if not paper.year: paper.year = "0000"
    if not paper.title: paper.title = "NoTitle"

    # 1. Surname
    try:
        surname = paper.authors.split(',')[0].split(' ')[-1]
        surname = re.sub(r'\W+', '', surname) # Remove non-alphanumeric
    except:
        surname = "Unknown"

    # 2. YEAR
    year_str = str(paper.year)

    # 3. Tit
    title_part = re.sub(r'[\s_]+', '', paper.title)[:3]

    base_key = f"{surname}{year_str}{title_part}"
    
    # 4. n (Disambiguation)
    final_key = base_key
    if base_key not in existing_keys:
        existing_keys[base_key] = 0
    else:
        existing_keys[base_key] += 1
        # Add 'a', 'b', etc. for disambiguation
        disambiguation_char = chr(ord('a') + existing_keys[base_key])
        # Also apply the first disambiguation char to the original entry
        if existing_keys[base_key] == 1:
           first_entry_key = f"{base_key}a"
           final_key = f"{base_key}b"
           return final_key, base_key # Return both to update the first entry
        else:
           final_key = f"{base_key}{disambiguation_char}"
    
    return final_key, None


def generate_custom_bibtex(papers, path):
    """
    Generates a single .bib file for a list of papers with custom keys.
    """
    print(f"Generating custom BibTeX file at: {path}")
    all_bib_entries = []
    key_counts = {}
    paper_key_map = {} # Maps paper index to final key

    # First pass to generate keys and handle disambiguation
    for i, p in enumerate(papers):
        if not p.bibtex:
            print(f"    Skipping paper without BibTeX info: {p.title}")
            continue

        final_key, original_key_to_update = generate_citekey(p, key_counts)

        if original_key_to_update:
            # Find the first paper that had this key and update it
            for j, old_p in enumerate(papers[:i]):
                if old_p.citekey == original_key_to_update:
                    paper_key_map[j] = f"{original_key_to_update}a"
                    break
        
        paper_key_map[i] = final_key
        p.citekey = final_key

    # Second pass to build the bib file with final keys
    for i, p in enumerate(papers):
        if p.bibtex:
            try:
                parser = bibtexparser.bparser.BibTexParser(common_strings=True)
                bib_database = bibtexparser.loads(p.bibtex, parser=parser)
                if bib_database.entries:
                    entry = bib_database.entries[0]
                    entry['ID'] = paper_key_map.get(i, entry['ID']) # Set custom key
                    all_bib_entries.append(entry)
            except Exception:
                continue
    
    final_db = bibtexparser.bibdatabase.BibDatabase()
    final_db.entries = all_bib_entries
    
    writer = bibtexparser.bwriter.BibTexWriter()
    writer.indent = '    ' # 4-space indentation
    with open(path, 'w', encoding='utf-8') as bibfile:
        bibfile.write(writer.write(final_db))

    print("BibTeX file generation complete.")