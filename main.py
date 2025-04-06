import requests
from bs4 import BeautifulSoup # type: ignore
from BookScraper import BookScraper 
import json

def get_page_links(page):
    
    results = []
    url = f'https://www.openbook.gr/page/{page}/?s'
    response = requests.get(url)

    # Check if the request was successful
    if response.status_code == 200:
        
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all the <a> tags within the specified class
            
            books= soup.find('div', class_='row b-row listing meta-below grid-3')  
            column_class = 'column one-third b-col'
            columns = books.find_all('div', class_=column_class)
            
            # Extract all <a> tags from each column
            
            for column in columns:
                links = column.find_all('a', class_ = 'image-link')
                
                for link in links:
                    results.append(link.get('href'))
                
            if len(results) > 21: 
                print(f"Found {len(results)} links on page {page}. More than 21 links found.")
                
            elif len(results) == 0:
                print(f"Fatal erorr: No links found on page {page}.")
                print('Stopping the program.')
                return False
                
                
            elif len(results) < 21:
                print(f"Found {len(results)} links on page {page}. Less than 21 links found.") 
                

            return results
                    
        except Exception as e:
            print(f"An error occurred in get page links main.py while parsing the page {page} Skipping this page: {e}")
            return []
    else:
        print(f"Failed to retrieve the webpage for page {page}. Status code: {response.status_code}")



def main():
    try:
        # Initialize page from file or start at 1
        try:
            with open('completed_pages.txt', 'r') as f:
                page = int(f.read().strip()) + 1  # Start from next page
        except FileNotFoundError:
            page = 1

        # Load existing data
        try:
            with open('books.json', 'r') as json_file:
                all_books_dict = json.load(json_file)
        except FileNotFoundError:
            all_books_dict = {}

        while True:
            print(f"Scraping page {page}...")
            links = get_page_links(page)
            if not links:
                print(f"No links found on page {page}. Stopping the program.")
                break
            
            for link in links:
                scraper = BookScraper(link)
                scraper.scrape()
                book_data_dict = scraper.to_dict()
                all_books_dict[scraper.book_key] = book_data_dict[scraper.book_key]

            # Save progress
            with open('completed_pages.txt', 'w') as f:
                f.write(str(page))
                
            # Save data
            with open('books.json', 'w') as json_file:
                json.dump(all_books_dict, json_file, indent=4, ensure_ascii=False)
                
            print(f"Saved and Scraped {len(all_books_dict)} books so far")
            page += 1 

    except Exception as e:
        print(f"An error occurred in main.py main: {e}")



if __name__ == "__main__":
    main()
    
