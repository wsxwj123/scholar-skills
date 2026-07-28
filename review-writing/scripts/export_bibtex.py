import json
import argparse
import sys
import os

from citation_utils import extract_citation_ids

def scan_used_ids(root_dir):
    """
    Scan markdown drafts for citation patterns [ID].
    Returns a set of used IDs (strings).
    """
    used_ids = set()
    if not os.path.exists(root_dir):
        print(f"Warning: Drafts directory not found at {root_dir}. Assuming no citations used.")
        return used_ids

    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(".md"):
                filepath = os.path.join(dirpath, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        used_ids.update(str(x) for x in extract_citation_ids(content))
                except Exception as e:
                    print(f"Warning: Could not read {filepath}: {e}")
    return used_ids

def export_to_bibtex(input_file, output_file, clean_mode=False, drafts_dir="drafts"):
    """
    Convert a literature index JSON file to a BibTeX .bib file.
    
    Args:
        input_file (str): Path to the input JSON file.
        output_file (str): Path to the output .bib file.
        clean_mode (bool): If True, only export citations used in drafts.
        drafts_dir (str): Directory containing drafts (used if clean_mode is True).
    """
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in {input_file}")
        sys.exit(1)

    # Ensure data is a list
    if isinstance(data, dict):
        # If the root is a dict, try to find a list of papers, 
        # otherwise assume the dict values are the items or it's a single item
        if "papers" in data:
            data = data["papers"]
        else:
            # Simple heuristic: if values are dicts, list them
            data = list(data.values())
    
    if not isinstance(data, list):
        print("Error: JSON structure expected to be a list of papers.")
        sys.exit(1)

    used_ids = set()
    if clean_mode:
        used_ids = scan_used_ids(drafts_dir)
        initial_count = len(data)

    bib_entries = []
    exported_count = 0
    
    for item in data:
        # Get Global ID for the citation key
        global_id = item.get('global_id')
        if not global_id:
            # Skip entries without global_id or handle them differently? 
            # For now, we skip to ensure mapping is correct.
            continue
        
        # In clean mode, skip if global_id is not in used_ids
        if clean_mode and str(global_id) not in used_ids:
            continue
            
        citation_key = f"ref_{global_id}"
        
        # Extract fields with safe defaults
        # BibTeX standard fields: author, title, journal, year, doi, volume, number, pages
        
        authors = item.get('authors', [])
        if isinstance(authors, list):
            author_str = " and ".join(authors)
        else:
            author_str = str(authors) # Fallback if string
            
        title = item.get('title', 'Unknown Title')
        journal = item.get('journal', 'Unknown Journal')
        year = item.get('year', '')
        doi = item.get('doi', '')
        
        # Construct the BibTeX entry
        entry_lines = []
        entry_lines.append(f"@article{{{citation_key},")
        entry_lines.append(f"  author = {{{author_str}}},")
        entry_lines.append(f"  title = {{{title}}},")
        entry_lines.append(f"  journal = {{{journal}}},")
        
        if year:
            entry_lines.append(f"  year = {{{year}}},")
        
        if doi:
            entry_lines.append(f"  doi = {{{doi}}},")
            
        # Add Global ID to note field for easy reference
        entry_lines.append(f"  note = {{Global ID: {global_id}}}")
        
        entry_lines.append("}")
        
        bib_entries.append("\n".join(entry_lines))
        exported_count += 1

    # Write output
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("\n\n".join(bib_entries))
        
        if clean_mode:
            skipped_count = initial_count - exported_count
            print(f"Found {initial_count} papers. Clean mode: Exported {exported_count} used citations ({skipped_count} skipped).")
        else:
            print(f"Successfully converted {exported_count} entries to {output_file}")
            
    except IOError as e:
        print(f"Error writing to output file: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Export literature index JSON to BibTeX.")
    parser.add_argument('--input', '-i', default='data/literature_index.json', 
                        help='Path to the input JSON file (default: data/literature_index.json)')
    parser.add_argument('--output', '-o', default='references.bib', 
                        help='Path to the output BibTeX file (default: references.bib)')
    parser.add_argument('--clean', action='store_true',
                        help='Only export citations that are actually used in the drafts directory.')
    parser.add_argument('--drafts-dir', default='drafts',
                        help='Directory to scan for used citations (default: drafts)')
    
    args = parser.parse_args()
    
    export_to_bibtex(args.input, args.output, args.clean, args.drafts_dir)

if __name__ == "__main__":
    main()
