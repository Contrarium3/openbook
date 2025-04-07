import json
import os
import asyncio
import aiohttp
import logging
import re
from pathlib import Path
from tqdm import tqdm
from urllib.parse import unquote, urlparse
import mimetypes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('book_downloader.log'),
        # logging.StreamHandler()  ## Not terminal
    ]
)
logger = logging.getLogger('book_downloader')

# Constants
DOWNLOAD_DIR = Path("downloads")
AUDIO_DIR = DOWNLOAD_DIR / "audio_books"
MOBILE_DIR = DOWNLOAD_DIR / "mobile_apps"

# Keywords for categorization
AUDIO_KEYWORDS = ["audio", "audio-book", "audio book", "ακούστε", "podcast", "mp3"]
MOBILE_KEYWORDS = ["android", "apple", "ios", "google play"]

# Identify document types from link names
DOCUMENT_TYPES = ["pdf", "epub", "kindle", "mobi", ".mobi", "διαβάστε", "κατεβάστε"]

# Types that may represent document volumes/parts
VOLUME_INDICATORS = [
    "τόμος", "τεύχος", "μέρος", "τόμ", "τευχ", "μερ", 
    "α'", "β'", "γ'", "δ'", "ε'", "στ'", "ζ'", "η'", 
    "1ος", "2ος", "3ος", "4ος", "5ος", "6ος", "7ος", "8ος", "9ος", "10ος",
    "1ο", "2ο", "3ο", "4ο", "5ο", "6ο", "7ο", "8ο", "9ο", "10ο",
    "v.1", "v.2", "v.3", "v.4", "v.5", "τόμος α", "τόμος β", "τόμος γ",
    "#1", "#2", "#3", "#4", "#5", "τεύχος 1", "τεύχος 2", "τεύχος 3"
]

# async def get_filename_from_response(response):
#     """Extract filename from Content-Disposition header or URL"""
#     content_disposition = response.headers.get('Content-Disposition')
#     if content_disposition:
#         filename_match = re.search(r'filename="?([^"]+)"?', content_disposition)
#         if filename_match:
#             return unquote(filename_match.group(1))
    
#     # If no filename in headers, extract from URL
#     url_path = urlparse(str(response.url)).path
#     filename = os.path.basename(url_path)
#     filename = filename.strip().replace('\n', ' ').replace('\r', '')

#     return unquote(filename)

MAX_FILENAME_LENGTH = 100  # safe limit

def shorten_filename(name):
    if len(name) > MAX_FILENAME_LENGTH:
        name = name[:MAX_FILENAME_LENGTH] + '...'
    return name

async def get_filename_from_response(response):
    content_disposition = response.headers.get("Content-Disposition", "")
    
    # Try to extract from filename*= (RFC 5987, properly encoded)
    match = re.search(r"filename\*\=UTF-8''(.+)", content_disposition)
    if match:
        filename_encoded = match.group(1)
        filename = unquote(filename_encoded)
        logger.info(f"Extracted filename from filename*=: {filename}")
        return shorten_filename(filename)

    # Fallback to old filename= (may be broken)
    match = re.search(r'filename="?(.*?)"?($|;)', content_disposition)
    if match:
        filename = match.group(1)
        logger.warning(f"Extracted filename from fallback filename=: {filename}")
        return shorten_filename(filename)

    # Final fallback to URL
    url_path = urlparse(str(response.url)).path
    filename = os.path.basename(url_path)
    logger.warning(f"Extracted filename from URL: {filename}")
    return shorten_filename(filename)


async def get_file_extension(response, url):
    """Determine file extension from content-type or URL"""
    content_type = response.headers.get('Content-Type', '')
    extension = mimetypes.guess_extension(content_type)
    
    if not extension or extension == '.bin':
        # Try to get extension from URL
        url_path = urlparse(url).path
        _, ext = os.path.splitext(url_path)
        if ext:
            return ext
            
        # Default extensions based on content type patterns
        if 'pdf' in content_type:
            return '.pdf'
        elif 'epub' in content_type:
            return '.epub'
        elif 'mobi' in content_type or 'x-mobipocket' in content_type:
            return '.mobi'
        return '.pdf'  # Default to PDF if nothing else works
    
    return extension

# async def download_file(session, url, destination_dir, link_name=None):
    """Download a file asynchronously and save it to the destination directory"""
    try:
        async with session.get(url) as response:
            if response.status == 200:
                # Get filename from response or generate one
                filename = await get_filename_from_response(response)
                
                # If filename is not valid or is empty, use link_name with extension
                if not filename or filename == '':
                    extension = await get_file_extension(response, url)
                    if link_name:
                        sanitized_link_name = re.sub(r'[\\/*?:"<>|]', '', link_name)
                        filename = f"{sanitized_link_name}{extension}"
                    else:
                        # Generate a filename based on URL hash if nothing else works
                        filename = f"file_{hash(url) % 10000}{extension}"
                
                # Create destination directory if it doesn't exist
                os.makedirs(destination_dir, exist_ok=True)
                
                # Full path to save the file
                file_path = os.path.join(destination_dir, filename)
                try:
                    file_path.encode('utf-8')  # Force check
                except UnicodeEncodeError:
                    filename = filename.encode('utf-8', 'ignore').decode('utf-8')  # fallback clean
                    file_path = os.path.join(destination_dir, filename)
                    logger.error(f"Filename {filename} contains invalid characters. Using fallback name.")

                
                # Save the file
                content = await response.read()
                with open(file_path, 'wb') as f:
                    f.write(content)
                
                logger.info(f"Downloaded {url} to {file_path}")
                return True, file_path
            else:
                logger.error(f"Failed to download {url}. Status code: {response.status}")
                return False, None
    except Exception as e:
        logger.error(f"Error downloading {url}: {str(e)}")
        return False, None





async def retry_with_backoff(coro_func, max_retries=3, initial_delay=2, backoff_factor=2):
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            return await coro_func()
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Retry {attempt + 1} failed. Retrying in {delay}s... Error: {e}")
                await asyncio.sleep(delay)
                delay *= backoff_factor
            else:
                raise e
            

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024 * 1024  # 20 GB

async def download_file(session, url, destination_dir, link_name=None):
    """Download a file asynchronously with retries, timeouts, chunked writing, and size check"""

    async def attempt():
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as response:
            if response.status != 200:
                raise Exception(f"Non-200 response: {response.status}")

            # Check content size
            content_length = response.headers.get('Content-Length')
            if content_length:
                file_size = int(content_length)
                if file_size > MAX_FILE_SIZE_BYTES:
                    logger.warning(f"Skipped {url} — File too large ({file_size / (1024**3):.2f} GB)")
                    return False, None
            else:
                logger.info(f"No Content-Length header for {url}. Proceeding anyway.")

            # Get filename from headers or fallback
            filename = await get_filename_from_response(response)
            if not filename or filename == '':
                extension = await get_file_extension(response, url)
                if link_name:
                    sanitized_link_name = re.sub(r'[\\/*?:"<>|]', '', link_name)
                    filename = f"{sanitized_link_name}{extension}"
                else:
                    filename = f"file_{hash(url) % 10000}{extension}"

            try:
                filename.encode('utf-8')  # Force check
            except UnicodeEncodeError:
                filename = filename.encode('utf-8', 'ignore').decode('utf-8')
                logger.error(f"Filename {filename} contained invalid characters. Cleaned fallback used.")

            os.makedirs(destination_dir, exist_ok=True)
            file_path = os.path.join(destination_dir, filename)

            # Save file in chunks
            with open(file_path, 'wb') as f:
                async for chunk in response.content.iter_chunked(1024 * 64):  # 64KB chunks
                    f.write(chunk)

            logger.info(f"Downloaded {url} to {file_path}")
            return True, file_path

    try:
        return await retry_with_backoff(attempt)
    except Exception as e:
        logger.error(f"Failed to download after retries: {url}. Error: {e}")
        return False, None




def is_audio_book(link_name):
    """Check if the link is for an audio book"""
    return any(keyword.lower() in link_name.lower() for keyword in AUDIO_KEYWORDS)

def is_mobile_app(link_name):
    """Check if the link is for a mobile app"""
    return any(keyword.lower() in link_name.lower() for keyword in MOBILE_KEYWORDS)

def is_document_link(link_name):
    """Check if the link is for a document to download"""
    return any(doc_type.lower() in link_name.lower() for doc_type in DOCUMENT_TYPES)

def is_volume_or_part(link_name):
    """Check if the link name indicates a volume or part of a book"""
    lower_link = link_name.lower()
    return any(indicator.lower() in lower_link for indicator in VOLUME_INDICATORS)

def should_download_all_volumes(book_links):
    """Determine if we should download all volumes for a book"""
    # Check if there are multiple volume indicators
    volume_count = sum(1 for link in book_links if is_volume_or_part(link))
    return volume_count > 0

async def process_book(session, book_title, book_data, progress_bar):
    """Process a single book: create folder and download files"""
    # Skip if already scraped
    if book_data.get("scraped", False):
        progress_bar.update(1)
        logger.info(f"Skipping {book_title} (already scraped)")
        return book_title, None
    links = book_data.get("links", {})
    
    # Check if book is audio book only (empty links {} are audio books)
    if not links:
        book_data["audio_book"] = True
        progress_bar.update(1)
        logger.info(f"Marked {book_title} as audio book (empty links)")
        return book_title, "audio_only"
    
    all_audio = all(is_audio_book(link_name) for link_name in links.keys())
    if all_audio:
        book_data["audio_book"] = True
        progress_bar.update(1)
        logger.info(f"Skipping {book_title} (audio book only)")
        return book_title, "audio_only"
    

    # Create sanitized folder name for the book
    folder_name = re.sub(r'[\\/*?:"<>|]', '', book_title)
    book_folder = DOWNLOAD_DIR / folder_name
    
    # Check if we should download all volumes
    download_all_volumes = should_download_all_volumes(links.keys())
    
    # Determine which links to download
    links_to_download = {}
    document_links = {}
    audio_links = {}
    mobile_links = {}
    
    # First, categorize all links
    for link_name, link_url in links.items():
        if is_audio_book(link_name):
            audio_links[link_name] = link_url
        elif is_mobile_app(link_name):
            mobile_links[link_name] = link_url
        elif is_document_link(link_name) or is_volume_or_part(link_name):
            document_links[link_name] = link_url
    
    # If no document links found, treat all non-audio, non-mobile links as documents
    if not document_links:
        for link_name, link_url in links.items():
            if link_name not in audio_links and link_name not in mobile_links:
                document_links[link_name] = link_url
    
    # If we should download all volumes or there are no volume indicators,
    # add all document links to download
    if download_all_volumes or not any(is_volume_or_part(link) for link in document_links):
        links_to_download.update(document_links)
    else:
        # Try to find the best link (PDF > EPUB > Kindle > other)
        best_link = None
        for priority in ["PDF", "ePub", "Kindle mobi", "Kindle", "Διαβάστε"]:
            for link_name, link_url in document_links.items():
                if priority.lower() in link_name.lower():
                    best_link = (link_name, link_url)
                    break
            if best_link:
                break
        
        # If no priority link found, use the first document link
        if not best_link and document_links:
            best_link = next(iter(document_links.items()))
        
        if best_link:
            links_to_download[best_link[0]] = best_link[1]
    
    # Remove links that don't end with dl=1
    valid_links_to_download = {name: url for name, url in links_to_download.items() if not url.endswith("dl=0") }
    
    # If no valid links to download, log and return
    if not valid_links_to_download:
        progress_bar.update(1)
        logger.warning(f"No valid download links found for {book_title}")
        return book_title, False
    
    # Download all selected document links
    download_tasks = []
    for link_name, link_url in valid_links_to_download.items():
        download_tasks.append(download_file(session, link_url, book_folder, link_name))
    
    # Download audio links to the audio folder
    for link_name, link_url in audio_links.items():
        if link_url.endswith("dl=1") or "dl=1" in link_url:
            audio_book_folder = AUDIO_DIR / folder_name
            download_tasks.append(download_file(session, link_url, audio_book_folder, link_name))
    
    # Save mobile links to the mobile folder (create files with links inside)
    for link_name, link_url in mobile_links.items():
        os.makedirs(MOBILE_DIR, exist_ok=True)
        mobile_file = MOBILE_DIR / f"{folder_name}_{link_name}.txt"
        with open(mobile_file, 'w', encoding='utf-8') as f:
            f.write(f"Title: {book_title}\nLink Type: {link_name}\nURL: {link_url}\n")
    
    # Execute all download tasks
    if download_tasks:
        download_results = await asyncio.gather(*download_tasks)
        successful_downloads = sum(1 for success, _ in download_results if success)
        
        if successful_downloads > 0:
            book_data["scraped"] = True
            if audio_links:
                book_data["has_audio"] = True
            if mobile_links:
                book_data["has_mobile_apps"] = True
            
            progress_bar.update(1)
            logger.info(f"Successfully downloaded {successful_downloads} files for {book_title}")
            return book_title, True
    
    progress_bar.update(1)
    logger.warning(f"Failed to download any files for {book_title}")
    return book_title, False

async def main():
    # Load the books data
    try:
        with open('books.json', 'r', encoding='utf-8') as f:
            books = json.load(f)
    except Exception as e:
        logger.error(f"Error loading books.json: {str(e)}")
        return
    
    # Create necessary directories
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    AUDIO_DIR.mkdir(exist_ok=True)
    MOBILE_DIR.mkdir(exist_ok=True)
    
    logger.info(f"Starting download of {len(books)} books")
    
    # Create a progress bar
    progress_bar = tqdm(total=len(books), desc="Processing books")
    
    # Process books
    async with aiohttp.ClientSession() as session:
        tasks = []
        
        for title, book_data in books.items():
            tasks.append(process_book(session, title, book_data, progress_bar))
            
        # Run downloads in parallel, with a limit of 100 concurrent downloads
        results = []
        for i in range(0, len(tasks), 100):
            batch = tasks[i:i+100]
            batch_results = await asyncio.gather(*batch)
            results.extend(batch_results)
            
            # Save updated books data after each batch to avoid losing progress
            with open('books.json', 'w', encoding='utf-8') as f:
                json.dump(books, f, ensure_ascii=False, indent=2)
    
    progress_bar.close()
    
    # Save final updated books data
    with open('books.json', 'w', encoding='utf-8') as f:
        json.dump(books, f, ensure_ascii=False, indent=2)
    
    # Print summary
    skipped = sum(1 for _, success in results if success is None)
    successful = sum(1 for _, success in results if success is True)
    audio_only = sum(1 for _, success in results if success == "audio_only")
    failed = sum(1 for _, success in results if success is False)
    
    logger.info(f"\nDownload summary:")
    logger.info(f"- {skipped} books already scraped and skipped")
    logger.info(f"- {successful} books downloaded successfully")
    logger.info(f"- {audio_only} books flagged as audio-only and skipped")
    logger.info(f"- {failed} books failed to download")
    logger.info(f"- {len(results)} books processed in total")

if __name__ == "__main__":
    asyncio.run(main())