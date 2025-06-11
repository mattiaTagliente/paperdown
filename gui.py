# gui.py
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog
import sys
import os
import threading
import json
import configparser
from pathlib import Path

from PyPaperBot.__main__ import start as standard_search_start
from PyPaperBot.RelevanceSearch import find_relevant_papers
from unpywall import Unpywall
from unpywall.utils import UnpywallCredentials
from unpywall.cache import UnpywallCache

CONFIG_FILE = 'config.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f: return json.load(f)
    return {}

def save_config(config_data):
    with open(CONFIG_FILE, 'w') as f: json.dump(config_data, f, indent=4)

def load_credentials():
    try:
        parser = configparser.ConfigParser()
        parser.read('credentials.txt')
        email = parser.get('credentials', 'email', fallback=None)
        s2_key = parser.get('credentials', 's2_api_key', fallback=None)
        if not email: raise ValueError("Email not found")
        return email, s2_key
    except Exception:
        return None, None

class App:
    def __init__(self, root, config):
        self.root = root
        self.config = config
        self.root.title("PyPaperBot Advanced")
        self.root.geometry("650x550")
        # ... (rest of __init__ is the same as the previous version) ...
        path_frame = tk.Frame(root, padx=10, pady=5)
        path_frame.pack(fill='x')
        tk.Label(path_frame, text="Download Folder:").pack(side='left')
        self.path_var = tk.StringVar(value=self.config.get("download_path", "Not Set"))
        tk.Label(path_frame, textvariable=self.path_var, fg="blue", wraplength=400).pack(side='left', padx=5)
        tk.Button(path_frame, text="Change...", command=self.select_download_path).pack(side='left')

        self.mode = tk.StringVar(value="standard")
        mode_frame = tk.Frame(root, padx=10, pady=5)
        mode_frame.pack(anchor='w')
        tk.Label(mode_frame, text="Search Mode:", font=('Helvetica', 10, 'bold')).pack(side='left')
        tk.Radiobutton(mode_frame, text="Standard Search", variable=self.mode, value="standard", command=self.toggle_mode).pack(side='left')
        tk.Radiobutton(mode_frame, text="Find Relevant Papers", variable=self.mode, value="relevant", command=self.toggle_mode).pack(side='left')
        
        self.standard_frame = tk.Frame(root, padx=10, pady=10)
        tk.Label(self.standard_frame, text="Enter Google Scholar Query or a single DOI:").pack(anchor='w')
        self.query_entry = tk.Entry(self.standard_frame, width=70)
        self.query_entry.pack(fill='x', pady=5)
        pages_frame = tk.Frame(self.standard_frame)
        pages_frame.pack(fill='x')
        tk.Label(pages_frame, text="Scholar Pages to Search:").pack(side='left')
        self.pages_entry = tk.Entry(pages_frame, width=5)
        self.pages_entry.insert(0, "1")
        self.pages_entry.pack(side='left', padx=5)

        self.relevant_frame = tk.Frame(root, padx=10, pady=10)
        tk.Label(self.relevant_frame, text="Topic:").pack(anchor='w')
        self.topic_entry = tk.Entry(self.relevant_frame, width=70)
        self.topic_entry.pack(fill='x', pady=5)
        
        controls_frame = tk.Frame(self.relevant_frame)
        controls_frame.pack(fill='x')
        
        tk.Label(controls_frame, text="Date Range:").pack(side='left')
        self.start_year_entry = tk.Entry(controls_frame, width=7)
        self.start_year_entry.insert(0, "2024")
        self.start_year_entry.pack(side='left', padx=5)
        tk.Label(controls_frame, text="-").pack(side='left')
        self.end_year_entry = tk.Entry(controls_frame, width=7)
        self.end_year_entry.insert(0, "2025")
        self.end_year_entry.pack(side='left', padx=10)

        tk.Label(controls_frame, text="# Reviews:").pack(side='left')
        self.num_reviews_entry = tk.Entry(controls_frame, width=4)
        self.num_reviews_entry.insert(0, "3")
        self.num_reviews_entry.pack(side='left', padx=5)

        tk.Label(controls_frame, text="# Non-Reviews:").pack(side='left')
        self.num_non_reviews_entry = tk.Entry(controls_frame, width=4)
        self.num_non_reviews_entry.insert(0, "6")
        self.num_non_reviews_entry.pack(side='left', padx=5)

        self.search_button = tk.Button(root, text="Search", command=self.start_search_thread, font=('Helvetica', 10, 'bold'))
        self.search_button.pack(pady=10)

        output_frame = tk.Frame(root, padx=10, pady=10)
        output_frame.pack(fill='both', expand=True)
        tk.Label(output_frame, text="Output Log:").pack(anchor='w')
        self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, state='disabled', bg='#f0f0f0')
        self.output_text.pack(fill='both', expand=True)
        sys.stdout = self.TextRedirector(self.output_text)

        self.toggle_mode()

    def toggle_mode(self):
        if self.mode.get() == "standard":
            self.relevant_frame.pack_forget()
            self.standard_frame.pack(fill='x', before=self.search_button)
        else:
            self.standard_frame.pack_forget()
            self.relevant_frame.pack(fill='x', before=self.search_button)

    def select_download_path(self):
        path = filedialog.askdirectory(title="Select Download Folder")
        if path:
            self.config["download_path"] = path
            save_config(self.config)
            self.path_var.set(path)

    def start_search_thread(self):
        if not self.config.get("download_path") or not os.path.isdir(self.config["download_path"]):
            messagebox.showerror("Error", "Please set a valid download folder first.")
            return

        self.search_button.config(state='disabled')
        threading.Thread(target=self.run_search, daemon=True).start()

    def run_search(self):
        self.output_text.config(state='normal')
        self.output_text.delete('1.0', tk.END)
        self.output_text.config(state='disabled')
        try:
            dwn_dir = self.config["download_path"]
            print(f"Using download directory: {dwn_dir}\n")

            if self.mode.get() == "standard":
                # ... standard search logic ...
                pass
            else:
                _, s2_api_key = load_credentials()
                find_relevant_papers(
                    topic=self.topic_entry.get(),
                    start_year=int(self.start_year_entry.get()),
                    end_year=int(self.end_year_entry.get()),
                    base_dwn_dir=dwn_dir,
                    num_reviews=int(self.num_reviews_entry.get()),
                    num_non_reviews=int(self.num_non_reviews_entry.get()),
                    s2_api_key=s2_api_key
                )
            messagebox.showinfo('Done!', 'Process finished.')
        except Exception as e:
            messagebox.showerror('Error', f'An error occurred:\n{e}')
        finally:
            self.search_button.config(state='normal')

    class TextRedirector:
        def __init__(self, w): self.widget = w
        def write(self, s):
            self.widget.config(state='normal')
            self.widget.insert(tk.END, s)
            self.widget.see(tk.END)
            self.widget.config(state='disabled')
        def flush(self): pass

def initialize_credentials():
    email, _ = load_credentials()
    if not email:
        messagebox.showerror("Credentials Error", "Could not find `email` in credentials.txt")
        return False
    UnpywallCredentials(email)
    
    # Ensure the main cache directory exists
    cache_dir = os.path.join(os.getcwd(), 'cache')
    os.makedirs(cache_dir, exist_ok=True)
    
    cache = UnpywallCache(os.path.join(cache_dir, 'unpaywall_cache'))
    Unpywall.init_cache(cache)
    return True

if __name__ == '__main__':
    if initialize_credentials():
        config = load_config()
        root = tk.Tk()
        app = App(root, config)
        if not config.get("download_path"): app.select_download_path()
        root.mainloop()