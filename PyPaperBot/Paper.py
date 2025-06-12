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
        self.downloadedFrom = 0
        
        self.use_doi_as_filename = False

    def getFileName(self):
        try:
            if self.use_doi_as_filename and self.DOI:
                return urllib.parse.quote(self.DOI, safe='') + ".pdf"
            else:
                # Use citekey for filename if available, otherwise title
                fname = self.citekey if self.citekey else self.title
                return re.sub(r'[^\w\-_. ]', '_', fname) + ".pdf"
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
        columns = ["Name", "Cite Key", "Scholar Link", "DOI", "Bibtex", "PDF Name", "Year", "Journal", "Downloaded", "Downloaded from", "Authors"]
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
                "Name": p.title, "Cite Key": p.citekey, "Scholar Link": p.scholar_link, "DOI": p.DOI,
                "Bibtex": bibtex_found, "PDF Name": pdf_name, "Year": p.year,
                "Journal": p.jurnal, "Downloaded": p.downloaded, "Downloaded from": dwn_from,
                "Authors": p.authors
            })
        df = pd.DataFrame(data, columns=columns)
        df.to_csv(path, index=False, encoding='utf-8')

# --- New Functionality for Custom BibTeX ---

def generate_citekeys(papers):
    """
    Generates and assigns a unique, robust citekey to each paper in a list
    based on the [SurnameYEARTitn] format.
    """
    key_counts = {}
    
    # First pass: Generate base keys and count frequencies
    for p in papers:
        try:
            surname = p.authors.split(',')[0].split(' ')[-1]
            surname = re.sub(r'\W+', '', surname)
        except (AttributeError, IndexError):
            surname = "Unknown"
        
        year_str = str(p.year) if p.year else "0000"
        
        source_str = p.title if p.title else p.jurnal
        if not source_str: source_str = "NoTitle"
        
        # Replace spaces with underscores and take first 3 chars
        title_part = source_str.replace(" ", "_")[:3]

        base_key = f"{surname}{year_str}{title_part}"
        p.citekey = base_key # Temporarily assign base key
        key_counts[base_key] = key_counts.get(base_key, 0) + 1

    # Second pass: Apply disambiguation where needed
    disambiguation_counters = {}
    for p in papers:
        base_key = p.citekey
        if key_counts.get(base_key, 0) > 1:
            # This key is a duplicate, so add a disambiguation letter
            current_count = disambiguation_counters.get(base_key, 0)
            p.citekey = f"{base_key}{chr(ord('a') + current_count)}"
            disambiguation_counters[base_key] = current_count + 1

    return papers


def generate_custom_bibtex(papers, path):
    """
    Generates a single .bib file for a list of papers with custom keys.
    This function now assumes papers have their 'citekey' attribute already set.
    """
    print(f"Generating custom BibTeX file at: {path}")
    all_bib_entries = []
    
    for p in papers:
        if p.bibtex:
            try:
                parser = bibtexparser.bparser.BibTexParser(common_strings=True)
                bib_database = bibtexparser.loads(p.bibtex, parser=parser)
                if bib_database.entries:
                    entry = bib_database.entries[0]
                    # Set the new, robust citekey
                    entry['ID'] = p.citekey if p.citekey else entry['ID']
                    all_bib_entries.append(entry)
            except Exception as e:
                print(f"    Warning: Could not parse bibtex for bibkey generation '{p.title}'. Reason: {e}")
                continue
    
    if all_bib_entries:
        final_db = bibtexparser.bibdatabase.BibDatabase()
        final_db.entries = all_bib_entries
        
        writer = bibtexparser.bwriter.BibTexWriter()
        writer.indent = '    '
        with open(path, 'w', encoding='utf-8') as bibfile:
            bibfile.write(writer.write(final_db))

    print("BibTeX file generation complete.")