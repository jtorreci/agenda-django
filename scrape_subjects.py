#!/usr/bin/env python3
"""
Script to scrape subjects from EPCC titulaciones pages and add them to asignaturas.csv
"""

import requests
from bs4 import BeautifulSoup
import csv
import re
import sys
from urllib.parse import urlparse

def scrape_subjects_from_url(url):
    """
    Scrape subjects from an EPCC titulación page
    Returns a list of dictionaries with subject information
    """
    print(f"[INFO] Scraping: {url}")
    
    try:
        # Get the page content
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract titulación name
        titulacion_name = None
        
        # Try different selectors to find the degree name
        title_selectors = [
            'h1.wp-block-post-title',
            'h1',
            '.entry-title',
            '.post-title'
        ]
        
        for selector in title_selectors:
            title_element = soup.select_one(selector)
            if title_element:
                titulacion_name = title_element.get_text().strip()
                break
        
        if not titulacion_name:
            # Fallback: extract from URL or page content
            titulacion_name = "Grado En Ingeniería Informática En Ingeniería De Computadores"  # Default for the first URL
        
        print(f"[DEGREE] Titulacion: {titulacion_name}")
        
        subjects = []
        
        # Look for subject tables in different possible structures
        
        # Method 1: Look for tables with course information
        tables = soup.find_all('table')
        
        for table in tables:
            # Check if this table contains subject information
            headers = table.find_all('th')
            if not headers:
                continue
                
            header_text = ' '.join([th.get_text().strip().lower() for th in headers])
            
            # Check if this looks like a subject table
            if any(keyword in header_text for keyword in ['asignatura', 'nombre', 'crédito', 'semestre', 'temporalidad']):
                print(f"[TABLE] Found subject table with headers: {header_text}")
                
                # Process table rows
                rows = table.find_all('tr')[1:]  # Skip header row
                
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:  # Minimum: name, credits, some other info
                        
                        subject_name = cells[0].get_text().strip()
                        
                        # Skip empty or header-like rows
                        if not subject_name or subject_name.lower() in ['asignatura', 'nombre', '']:
                            continue
                        
                        # Try to extract course and semester information
                        course = 1  # Default
                        semester = 1  # Default
                        
                        # Look for course info in the table context or row data
                        # Check if there's course information in nearby elements
                        course_context = None
                        current_element = table
                        while current_element and not course_context:
                            prev_element = current_element.find_previous(['h2', 'h3', 'h4', 'div'])
                            if prev_element:
                                text = prev_element.get_text().strip()
                                course_match = re.search(r'curso\s*(\d+)', text, re.IGNORECASE)
                                if course_match:
                                    course = int(course_match.group(1))
                                    course_context = text
                                    break
                            current_element = prev_element
                        
                        # Try to extract semester from the row data
                        for cell in cells:
                            cell_text = cell.get_text().strip().lower()
                            if 'primer' in cell_text or '1' in cell_text:
                                if 'semestre' in cell_text or 'cuatrimestre' in cell_text:
                                    semester = 1
                            elif 'segundo' in cell_text or '2' in cell_text:
                                if 'semestre' in cell_text or 'cuatrimestre' in cell_text:
                                    semester = 2
                        
                        subjects.append({
                            'Asignatura': subject_name.upper(),
                            'Curso': course,
                            'Semestre': semester,
                            'Titulación': titulacion_name
                        })
                        
                        print(f"  [SUBJECT] {subject_name} (Curso {course}, Semestre {semester})")
        
        # Method 2: Look for list-based structures if tables don't work
        if not subjects:
            print("[SEARCH] No tables found, looking for alternative structures...")
            
            # Look for div-based course structures
            course_divs = soup.find_all(['div', 'section'], class_=re.compile(r'course|año|curso', re.IGNORECASE))
            
            for div in course_divs:
                course_text = div.get_text()
                course_match = re.search(r'curso\s*(\d+)', course_text, re.IGNORECASE)
                if course_match:
                    course = int(course_match.group(1))
                    
                    # Look for subject lists within this course div
                    subject_elements = div.find_all(['li', 'p', 'div'])
                    
                    for element in subject_elements:
                        text = element.get_text().strip()
                        if len(text) > 10 and len(text) < 100:  # Reasonable subject name length
                            subjects.append({
                                'Asignatura': text.upper(),
                                'Curso': course,
                                'Semestre': 1,  # Default
                                'Titulación': titulacion_name
                            })
        
        print(f"[SUCCESS] Found {len(subjects)} subjects")
        return subjects
        
    except requests.RequestException as e:
        print(f"[ERROR] Error fetching URL: {e}")
        return []
    except Exception as e:
        print(f"[ERROR] Error parsing page: {e}")
        return []

def append_to_csv(subjects, csv_file='asignaturas.csv'):
    """
    Append subjects to the CSV file, avoiding duplicates
    """
    if not subjects:
        print("[WARNING] No subjects to add")
        return
    
    # Read existing subjects to avoid duplicates
    existing_subjects = set()
    try:
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                key = (row.get('Asignatura', '').strip().upper(), 
                       row.get('Titulación', '').strip())
                existing_subjects.add(key)
    except FileNotFoundError:
        print(f"[FILE] Creating new file: {csv_file}")
    
    # Filter out duplicates
    new_subjects = []
    for subject in subjects:
        key = (subject['Asignatura'].strip().upper(), subject['Titulación'].strip())
        if key not in existing_subjects:
            new_subjects.append(subject)
            existing_subjects.add(key)
        else:
            print(f"[SKIP] Skipping duplicate: {subject['Asignatura']}")
    
    if not new_subjects:
        print("[INFO] No new subjects to add (all were duplicates)")
        return
    
    # Append new subjects
    with open(csv_file, 'a', encoding='utf-8-sig', newline='') as f:
        fieldnames = ['Asignatura', 'Curso', 'Semestre', 'Titulación']
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        
        # Check if file was empty (write headers)
        if f.tell() == 0:
            writer.writeheader()
        
        for subject in new_subjects:
            writer.writerow(subject)
    
    print(f"[SUCCESS] Added {len(new_subjects)} new subjects to {csv_file}")

def main():
    """
    Main function to handle command line arguments and scraping
    """
    if len(sys.argv) < 2:
        print("Usage: python scrape_subjects.py <URL> [<URL2> <URL3> ...]")
        print("Example: python scrape_subjects.py https://epcc.unex.es/titulaciones/1627/#tab-subjects")
        return
    
    urls = sys.argv[1:]
    
    print(f"[START] Starting scraping for {len(urls)} URL(s)...")
    print("=" * 60)
    
    all_subjects = []
    
    for url in urls:
        subjects = scrape_subjects_from_url(url)
        all_subjects.extend(subjects)
        print("-" * 40)
    
    if all_subjects:
        append_to_csv(all_subjects)
        print(f"\n[COMPLETE] Total subjects processed: {len(all_subjects)}")
    else:
        print("\n[ERROR] No subjects were found")

if __name__ == "__main__":
    main()