import requests
import json
import sys
import re
import time
from urllib.parse import quote, urlparse, parse_qs

class EnhancedMediaDownloader:
    def __init__(self):
        self.tmdb_api_key = "YOUR_TMDB_API_KEY"  # Get from https://www.themoviedb.org/signup
        self.base_url = "https://vidvault.ru"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def search_tmdb(self, query, media_type="movie"):
        """Search TMDb for a movie or TV show by name"""
        if not self.tmdb_api_key or self.tmdb_api_key == "YOUR_TMDB_API_KEY":
            print("⚠️  Please set your TMDb API key in the script")
            print("Get one for free at: https://www.themoviedb.org/signup")
            return None
        
        search_url = "https://api.themoviedb.org/3/search/{media_type}"
        
        params = {
            'api_key': self.tmdb_api_key,
            'query': query,
            'language': 'en-US',
            'page': 1,
            'include_adult': False
        }
        
        try:
            response = requests.get(search_url.format(media_type=media_type), params=params)
            if response.status_code == 200:
                data = response.json()
                if data.get('results'):
                    return data['results']
                else:
                    print(f"No results found for '{query}'")
                    return None
            else:
                print(f"Error searching TMDb: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error: {e}")
            return None
    
    def display_results(self, results, media_type="movie"):
        """Display search results in a readable format"""
        if not results:
            return None
        
        print(f"\n{'='*60}")
        print(f"🔍 Search Results ({len(results)} found):")
        print('='*60)
        
        for idx, item in enumerate(results, 1):
            title = item.get('title' if media_type == 'movie' else 'name', 'Unknown')
            year = item.get('release_date' if media_type == 'movie' else 'first_air_date', '')
            if year:
                year = year[:4]
            else:
                year = 'N/A'
            
            tmdb_id = item.get('id')
            overview = item.get('overview', '')
            if overview:
                overview = overview[:100] + '...' if len(overview) > 100 else overview
            
            print(f"\n{idx}. {title} ({year})")
            print(f"   TMDb ID: {tmdb_id}")
            print(f"   Overview: {overview}")
        
        print('='*60)
        return results
    
    def get_user_choice(self, results):
        """Let user choose from search results"""
        while True:
            try:
                choice = input("\n📝 Enter the number of the item you want (or 'q' to quit): ").strip()
                
                if choice.lower() == 'q':
                    return None
                
                choice_num = int(choice)
                if 1 <= choice_num <= len(results):
                    return results[choice_num - 1]
                else:
                    print(f"Please enter a number between 1 and {len(results)}")
            except ValueError:
                print("Please enter a valid number")
    
    def get_download_links_alternative(self, tmdb_id, media_type="movie"):
        """Try alternative methods to get download links"""
        links = []
        
        # Method 1: Try the main search with different parameters
        methods = [
            # Direct search
            {'url': f"{self.base_url}/search", 'data': {'type': media_type, 'id': tmdb_id}},
            # Alternative endpoint
            {'url': f"{self.base_url}/api/search", 'data': {'type': media_type, 'id': tmdb_id}},
            # With different parameter names
            {'url': f"{self.base_url}/search", 'data': {'media_type': media_type, 'tmdb_id': tmdb_id}},
            # GET request instead of POST
            {'url': f"{self.base_url}/search?type={media_type}&id={tmdb_id}", 'method': 'GET'},
        ]
        
        for method in methods:
            try:
                print(f"🔄 Trying: {method.get('url', '')}")
                
                if method.get('method', 'POST') == 'GET':
                    response = self.session.get(method['url'])
                else:
                    response = self.session.post(method['url'], data=method['data'])
                
                if response.status_code == 200:
                    # Try to parse as JSON
                    try:
                        data = response.json()
                        if data and isinstance(data, dict):
                            # Check for links in various places
                            for key in ['links', 'download_links', 'results', 'data']:
                                if key in data:
                                    if isinstance(data[key], list):
                                        links.extend(data[key])
                                    elif isinstance(data[key], dict):
                                        links.extend([v for v in data[key].values() if isinstance(v, str)])
                    except:
                        # Parse HTML for links
                        html_links = self.extract_links_from_html(response.text)
                        links.extend(html_links)
                    
                    if links:
                        break
            except Exception as e:
                continue
        
        return list(set(links))
    
    def get_download_links(self, tmdb_id, media_type="movie"):
        """Get download links from vidvault.ru with enhanced methods"""
        links = []
        
        # Try multiple methods
        print(f"\n🔄 Fetching download links for TMDb ID: {tmdb_id}...")
        
        # Method 1: Standard POST
        try:
            search_url = f"{self.base_url}/search"
            payload = {
                'type': media_type,
                'id': tmdb_id
            }
            
            response = self.session.post(search_url, data=payload)
            
            if response.status_code == 200:
                print("✅ Successfully connected to server")
                
                # Try to parse JSON
                try:
                    data = response.json()
                    if data:
                        print(f"📊 Response data: {json.dumps(data, indent=2)[:500]}...")
                        # Extract links from JSON
                        if isinstance(data, dict):
                            for key in ['links', 'download_links', 'urls', 'results']:
                                if key in data:
                                    if isinstance(data[key], list):
                                        links.extend(data[key])
                                    elif isinstance(data[key], dict):
                                        links.extend([v for v in data[key].values() if isinstance(v, str)])
                        elif isinstance(data, list):
                            links.extend(data)
                except:
                    # Not JSON, parse HTML
                    html_links = self.extract_links_from_html(response.text)
                    links.extend(html_links)
                    
                    # Also look for iframe and embed sources
                    iframe_links = self.extract_iframe_sources(response.text)
                    links.extend(iframe_links)
        except Exception as e:
            print(f"⚠️  Error with standard method: {e}")
        
        # Method 2: Try alternative methods if no links found
        if not links:
            print("🔄 Trying alternative methods...")
            alt_links = self.get_download_links_alternative(tmdb_id, media_type)
            links.extend(alt_links)
        
        # Method 3: Try to find using the movie title from TMDb
        if not links:
            print("🔄 Trying to search by title...")
            title_links = self.search_by_title(tmdb_id, media_type)
            links.extend(title_links)
        
        # Remove duplicates and filter
        links = list(set(links))
        filtered_links = []
        for link in links:
            if link and isinstance(link, str):
                # Filter out common non-download links
                if not any(x in link.lower() for x in ['google', 'facebook', 'twitter', 'youtube', 'analytics', 'javascript:', '#']):
                    if link.startswith('http'):
                        filtered_links.append(link)
        
        return filtered_links
    
    def search_by_title(self, tmdb_id, media_type="movie"):
        """Try to find links by searching with the title"""
        links = []
        
        try:
            # Get movie details from TMDb
            if self.tmdb_api_key and self.tmdb_api_key != "YOUR_TMDB_API_KEY":
                url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}"
                params = {'api_key': self.tmdb_api_key, 'language': 'en-US'}
                response = requests.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    title = data.get('title' if media_type == 'movie' else 'name', '')
                    year = data.get('release_date' if media_type == 'movie' else 'first_air_date', '')[:4]
                    
                    if title:
                        print(f"🎬 Searching for: {title} ({year})")
                        
                        # Try searching with title on vidvault
                        search_url = f"{self.base_url}/search"
                        payload = {'query': f"{title} {year}", 'type': media_type}
                        response = self.session.post(search_url, data=payload)
                        
                        if response.status_code == 200:
                            html_links = self.extract_links_from_html(response.text)
                            links.extend(html_links)
        except Exception as e:
            print(f"⚠️  Error in title search: {e}")
        
        return links
    
    def extract_links_from_html(self, html_content):
        """Extract download links from HTML response"""
        if not html_content:
            return []
        
        links = []
        
        # Pattern for various link formats
        patterns = [
            # Video file extensions
            r'href="(https?://[^"]+\.(mp4|mkv|avi|mov|wmv|flv|webm|3gp|m4v))"',
            r'src="(https?://[^"]+\.(mp4|mkv|avi|mov|wmv|flv|webm|3gp|m4v))"',
            # Torrent files
            r'href="(https?://[^"]+\.(torrent))"',
            # Download links with keywords
            r'href="(https?://[^"]*(?:download|media|video|movie|file|stream)[^"]*)"',
            # Direct links to video hosting sites
            r'data-url="(https?://[^"]+)"',
            r'data-href="(https?://[^"]+)"',
            # Common video hosting patterns
            r'(https?://(?:www\.)?(?:youtube\.com|vimeo\.com|dailymotion\.com|drive\.google\.com|mega\.nz)/[^\s"\'<>]+)',
            # Any HTTP URL that might be a media file
            r'(https?://[^\s"\'<>]+\.(?:mp4|mkv|avi|mov))',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    link = match[0] if match else None
                else:
                    link = match
                if link and link.startswith('http'):
                    links.append(link)
        
        return links
    
    def extract_iframe_sources(self, html_content):
        """Extract iframe sources which might contain video players"""
        if not html_content:
            return []
        
        links = []
        patterns = [
            r'<iframe[^>]+src="([^"]+)"',
            r'<embed[^>]+src="([^"]+)"',
            r'<video[^>]+src="([^"]+)"',
            r'<source[^>]+src="([^"]+)"',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                if match and match.startswith('http'):
                    links.append(match)
        
        return links
    
    def download_file(self, url, filename=None):
        """Download a file from URL with progress"""
        try:
            print(f"\n📥 Downloading: {url}")
            
            # Get filename from URL if not provided
            if not filename:
                filename = url.split('/')[-1]
                if not filename or '.' not in filename:
                    filename = f"download_{int(time.time())}.mp4"
            
            # Check if it's a streamable link
            if 'm3u8' in url.lower():
                print("⚠️  This is a streaming link (m3u8). Use a streaming downloader.")
                return False
            
            # Add headers for download
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Referer': self.base_url,
            }
            
            response = self.session.get(url, stream=True, headers=headers)
            
            if response.status_code == 200:
                total_size = int(response.headers.get('content-length', 0))
                block_size = 8192
                
                with open(filename, 'wb') as file:
                    downloaded = 0
                    print(f"📊 Downloading {filename}...")
                    for chunk in response.iter_content(chunk_size=block_size):
                        if chunk:
                            file.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                percent = (downloaded / total_size) * 100
                                bar_length = 40
                                filled = int(bar_length * downloaded // total_size)
                                bar = '█' * filled + '░' * (bar_length - filled)
                                print(f'\r[{bar}] {percent:.1f}%', end='')
                
                print(f"\n✅ Downloaded: {filename}")
                return True
            else:
                print(f"❌ Failed to download: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error downloading: {e}")
            return False
    
    def process_download_links(self, tmdb_id, media_type, title):
        """Process download links for a given TMDb ID"""
        links = self.get_download_links(tmdb_id, media_type)
        
        if not links:
            print("\n❌ No download links found")
            print("\n💡 Possible reasons:")
            print("  1. The movie/TV show is not available on this site")
            print("  2. The site structure has changed")
            print("  3. The TMDb ID might be incorrect")
            print("\n🔧 You can try:")
            print("  • Check if the movie is available on vidvault.ru manually")
            print("  • Try with the IMDb ID instead")
            print("  • Try with a different search term")
            return
        
        print(f"\n📎 Found {len(links)} download link(s):")
        for idx, link in enumerate(links, 1):
            # Truncate long links for display
            display_link = link[:80] + '...' if len(link) > 80 else link
            print(f"  {idx}. {display_link}")
        
        # Ask if user wants to download
        download_choice = input("\n📥 Download? (yes/no/all): ").strip().lower()
        
        if download_choice == 'all':
            for idx, link in enumerate(links, 1):
                safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
                filename = f"{safe_title}_{idx}.mp4"
                self.download_file(link, filename)
        elif download_choice in ['yes', 'y']:
            if len(links) > 1:
                link_num = input(f"Which link to download (1-{len(links)}): ").strip()
                try:
                    link_idx = int(link_num) - 1
                    if 0 <= link_idx < len(links):
                        safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
                        filename = f"{safe_title}.mp4"
                        self.download_file(links[link_idx], filename)
                    else:
                        print("❌ Invalid link number")
                except ValueError:
                    print("❌ Invalid input")
            else:
                safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
                filename = f"{safe_title}.mp4"
                self.download_file(links[0], filename)
    
    def interactive_search_and_download(self):
        """Main interactive function"""
        print("\n" + "="*60)
        print("🎬 Enhanced Media Downloader - Search & Download")
        print("="*60)
        
        # Check for API key
        if self.tmdb_api_key == "YOUR_TMDB_API_KEY":
            print("\n⚠️  TMDb API Key not configured!")
            print("   Without API key, you can still use direct TMDb/IMDb IDs.")
            print("   Get a free API key at: https://www.themoviedb.org/signup")
            api_key = input("\nEnter your TMDb API key (or press Enter to skip): ").strip()
            if api_key:
                self.tmdb_api_key = api_key
        
        while True:
            print("\n📋 Options:")
            print("  1. Search by name")
            print("  2. Enter TMDb ID directly")
            print("  3. Enter IMDb ID directly")
            print("  4. Try manual URL (advanced)")
            print("  5. Exit")
            
            choice = input("\n👉 Select option (1-5): ").strip()
            
            if choice == '1':
                self.search_by_name_flow()
            elif choice == '2':
                self.direct_tmdb_flow()
            elif choice == '3':
                self.direct_imdb_flow()
            elif choice == '4':
                self.manual_url_flow()
            elif choice == '5':
                print("\n👋 Goodbye!")
                break
            else:
                print("❌ Invalid option. Please try again.")
    
    def search_by_name_flow(self):
        """Flow for searching by name"""
        media_type = input("\n🎯 Media type (movie/tv): ").strip().lower()
        if media_type not in ['movie', 'tv']:
            print("❌ Invalid type. Defaulting to 'movie'")
            media_type = 'movie'
        
        search_query = input(f"\n🔍 Enter {media_type} name: ").strip()
        if not search_query:
            print("❌ No search query entered")
            return
        
        # Search TMDb
        results = self.search_tmdb(search_query, media_type)
        if not results:
            return
        
        # Display results
        self.display_results(results, media_type)
        
        # Get user choice
        selected = self.get_user_choice(results)
        if not selected:
            return
        
        tmdb_id = selected.get('id')
        title = selected.get('title' if media_type == 'movie' else 'name', 'Unknown')
        
        print(f"\n✅ Selected: {title} (TMDb ID: {tmdb_id})")
        
        # Get download links
        self.process_download_links(tmdb_id, media_type, title)
    
    def direct_tmdb_flow(self):
        """Flow for direct TMDb ID input"""
        tmdb_id = input("\n🔢 Enter TMDb ID: ").strip()
        if not tmdb_id:
            print("❌ No ID entered")
            return
        
        if not tmdb_id.isdigit():
            print("❌ Invalid TMDb ID. Must be a number.")
            return
        
        media_type = input("🎯 Media type (movie/tv): ").strip().lower()
        if media_type not in ['movie', 'tv']:
            print("❌ Invalid type. Defaulting to 'movie'")
            media_type = 'movie'
        
        self.process_download_links(tmdb_id, media_type, f"TMDb-{tmdb_id}")
    
    def direct_imdb_flow(self):
        """Flow for direct IMDb ID input"""
        imdb_id = input("\n🔢 Enter IMDb ID (e.g., tt0137523): ").strip()
        if not imdb_id:
            print("❌ No ID entered")
            return
        
        if not imdb_id.startswith('tt'):
            print("❌ Invalid IMDb ID. Must start with 'tt'")
            return
        
        # Try to convert IMDb to TMDb
        result = None
        if self.tmdb_api_key and self.tmdb_api_key != "YOUR_TMDB_API_KEY":
            try:
                url = f"https://api.themoviedb.org/3/find/{imdb_id}"
                params = {
                    'api_key': self.tmdb_api_key,
                    'external_source': 'imdb_id'
                }
                response = requests.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    # Check both movie and TV results
                    for media_type in ['movie_results', 'tv_results']:
                        if data.get(media_type) and data[media_type]:
                            result = data[media_type][0]
                            break
            except:
                pass
        
        if result:
            tmdb_id = result.get('id')
            title = result.get('title' if 'title' in result else 'name', imdb_id)
            media_type = 'movie' if 'title' in result else 'tv'
            
            print(f"\n✅ Found: {title} (TMDb ID: {tmdb_id})")
            self.process_download_links(tmdb_id, media_type, title)
        else:
            print("❌ Could not find TMDb ID for this IMDb ID")
            # Try to use IMDb ID directly
            print("🔄 Trying with IMDb ID directly...")
            self.process_download_links(imdb_id, 'movie', imdb_id)
    
    def manual_url_flow(self):
        """Manual URL entry for testing"""
        print("\n🔗 Enter the full URL from vidvault.ru (e.g., https://vidvault.ru/movie/12345)")
        url = input("URL: ").strip()
        
        if not url:
            return
        
        try:
            response = self.session.get(url)
            if response.status_code == 200:
                links = self.extract_links_from_html(response.text)
                iframe_links = self.extract_iframe_sources(response.text)
                links.extend(iframe_links)
                
                if links:
                    print(f"\n📎 Found {len(links)} link(s):")
                    for idx, link in enumerate(links, 1):
                        display_link = link[:80] + '...' if len(link) > 80 else link
                        print(f"  {idx}. {display_link}")
                    
                    download = input("\n📥 Download first link? (yes/no): ").strip().lower()
                    if download in ['yes', 'y']:
                        self.download_file(links[0])
                else:
                    print("❌ No links found on the page")
            else:
                print(f"❌ Error: {response.status_code}")
        except Exception as e:
            print(f"❌ Error: {e}")

def main():
    """Main function"""
    downloader = EnhancedMediaDownloader()
    
    # Check command line arguments
    if len(sys.argv) > 1:
        # Command line mode
        query = sys.argv[1]
        media_type = sys.argv[2] if len(sys.argv) > 2 else "movie"
        
        # Check if it's an ID or name
        if query.isdigit():
            # TMDb ID
            downloader.process_download_links(query, media_type, f"TMDb-{query}")
        elif query.startswith('tt'):
            # IMDb ID
            downloader.direct_imdb_flow()
        else:
            # Search by name
            results = downloader.search_tmdb(query, media_type)
            if results:
                downloader.display_results(results, media_type)
                selected = downloader.get_user_choice(results)
                if selected:
                    tmdb_id = selected.get('id')
                    title = selected.get('title' if media_type == 'movie' else 'name', 'Unknown')
                    downloader.process_download_links(tmdb_id, media_type, title)
    else:
        # Interactive mode
        downloader.interactive_search_and_download()

if __name__ == "__main__":
    main()