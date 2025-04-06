import requests
from bs4 import BeautifulSoup # type: ignore
import json
import html
import re


class BookScraper:
    def __init__(self, url=None):
        if url:
            self.url = url
            self.book_key = url.split('/')[-2] if url[-1] == '/' else url.split('/')[-1]
            self.book_dict = {
                self.book_key: {
                    'links': {},
                    'metadata': {}
                }
            }
        else:
            self.url = None
            self.book_key = None
            self.book_dict = {}
        
    def scrape(self, url=None):
        
        try:
            if url:
                self.url = url
                self.book_key = url.split('/')[-2] if url[-1] == '/' else url.split('/')[-1]
                self.book_dict = {
                    self.book_key: {
                        'links': {},
                        'metadata': {}
                    }
                }
                
            if not self.url:
                raise ValueError("URL is required for scraping")
                
            response = requests.get(self.url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all links with class that starts with 'wpcmsdev-button'
            links = soup.find_all('a', class_=lambda c: c and c.startswith('wpcmsdev-button'))
            
            # Add the links to the dictionary
            for i, link in enumerate(links):
                link_url = link.get('href')
                type =  html.unescape( link.text.strip()) # pdf or epub or kindle or Android or Apple

                self.book_dict[self.book_key]['links'][type] = link_url
                
            self.scrape_metadata(soup)
                
            return self.book_dict
        
        except Exception as e:
            print(f"An error occurred in Book scraper scrape : {e}")
            return None
        
    def scrape_metadata(self, soup):
        try:
            # Get the title
            title_element = soup.find('h1', class_='post-title')
            if title_element:
                self.book_dict[self.book_key]['metadata']['h1'] = title_element.text.strip()
            
            # Get all paragraphs in the content area
            content_area = soup.find('div', class_='post-content')
            if content_area:
                paragraphs = content_area.find_all('p')
                
                # Process each paragraph to extract metadata
                for p in paragraphs:
                    text = p.text.strip()
                    
                    if text.startswith('Συγγραφέας:'):
                        self.book_dict[self.book_key]['metadata']['author'] = text.replace('Συγγραφέας:', '').strip()
                        
                    elif text.startswith('Τίτλος:'):
                        self.book_dict[self.book_key]['metadata']['title'] = text.replace('Τίτλος:', '').strip()
                    
                    
                    elif text.startswith('Μετάφραση'):
                        self.book_dict[self.book_key]['metadata']['translator'] = text.replace('Μετάφραση από τα ισπανικά:', '').strip()
                    
                    # elif text.startswith('Άδεια διανομής:'):
                    #     self.book_dict[self.book_key]['metadata']['license'] = text.replace('Άδεια διανομής:', '').strip()
                    
                    elif text.startswith('ISBN'):
                        self.book_dict[self.book_key]['metadata']['isbn'] = text.replace('ISBN', '').strip()
                    


                    # etos eksodhs to key 'h etos a ekdoshs h etos b ekdoshs
                    if 'Σελίδες:' in text and 'Έτος' in text:
                        parts = text.split('//')
                        if len(parts) == 2:
                            pages_part = parts[0].strip()
                            year_part = html.unescape(parts[1].strip())

                            # Extract pages
                            pages = pages_part.replace('Σελίδες:', '').strip()

                            # Match everything after 'Έτος'
                            match = re.search(r"(Έτος.*?):\s*(.*)", year_part)


                            if match:
                                # Extract the key (everything before the colon)
                                key = match.group(1)  
                                value = match.group(2) 
                                self.book_dict[self.book_key]['metadata'][key] = value
                                
                            else:
                                print('No match found for year extraction in book.py')

                            self.book_dict[self.book_key]['metadata']['pages'] = pages

                    elif text.startswith('Σελίδες'):
                        self.book_dict[self.book_key]['metadata']['pages'] = text.replace('Σελίδες:', '').strip()

                    elif text.startswith('Έτος'):
                    # Match everything after 'Έτος'
                        match = re.search(r"(Έτος.*?):\s*(.*)", text)


                        if match:
                            # Extract the key (everything before the colon)
                            key = match.group(1)  
                            value = match.group(2)  
                            self.book_dict[self.book_key]['metadata'][key] = value
                            
                        else:
                            print('No match found for year extraction in book.py')
                            
                    
                    elif text.startswith('Είδος'):
                        self.book_dict[self.book_key]['metadata']['type'] = text.replace('Είδος:', '').strip()
                
                # Get the description
                description = content_area.find('blockquote')
                if description:
                    self.book_dict[self.book_key]['metadata']['description'] = description.text.strip()
            
            # Get tags
            tags_div = soup.find('div', class_='tagcloud')
            if tags_div:
                tags = [tag.text.strip() for tag in tags_div.find_all('a')]
                self.book_dict[self.book_key]['metadata']['tags'] = tags
            

            return self.book_dict
        
        except Exception as e:
            print(f"An error occurred in Book scraper scrape_metadata : {e}")
            return {}

    def to_dict(self):
        return self.book_dict