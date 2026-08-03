import os
import json
import subprocess
import uuid
from datetime import datetime
from functools import wraps
from pathlib import Path
import re
import requests

from flask import Flask, render_template, jsonify, request, send_from_directory, session, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = 'change-this-to-a-random-secret-key'

# ===== CONFIGURATION =====
VIDEO_FOLDER = r"C:\Users\mss happy\Desktop\Fartuun Aroos"
UPLOAD_FOLDER = os.path.join(VIDEO_FOLDER, "uploads")
THUMBNAIL_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "thumbnails")
JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "videos.json")

ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'webm'}
MAX_CONTENT_LENGTH = 20 * 1024 * 1024 * 1024
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
MAX_DURATION_SEC = 20 * 3600

ADMIN_PASSWORD = "123yy"

# ===== TMDB CONFIGURATION =====
TMDB_API_KEY = 'aadf6860bbcd42aec429b940c962cf7a'
TMDB_ACCESS_TOKEN = 'eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJhYWRmNjg2MGJiY2Q0MmFlYzQyOWI5NDBjOTYyY2Y3YSIsIm5iZiI6MTc4NTQzMjM4Mi43NTIsInN1YiI6IjZhNmI4OTNlZjg4ODc5NTU0NjNmMDAyOSIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.vRVVehSkd_v4qHDdqQIHJno0DQ-x34SnMuvJUnGLD0g'
TMDB_BASE_URL = 'https://api.themoviedb.org/3'

# ===== SERVER CONFIGURATION =====
# Server 1: SuperEmbed (Recommended)
SUPEREMBED_BASE_URL = 'https://multiembed.mov'
SUPEREMBED_SERVERS = {
    'primary': 'https://multiembed.mov',
    'vip': 'https://multiembed.mov/directstream.php',
}

# Server 2: Vidsrc (Existing)
VIDSRC_DOMAINS = ['vidsrc.mov', 'embed.vidsrc.mov', 'vidsrc.cc', 'vidsrc.pm', 'vidsrc.to']

# Genre mappings for TMDB
GENRE_MAP = {
    'action': 28,
    'animation': 16,
    'horror': 27,
    'comedy': 35,
    'drama': 18,
    'documentary': 99,
    'science_fiction': 878,
    'thriller': 53,
    'romance': 10749,
    'adventure': 12,
    'fantasy': 14,
    'family': 10751,
    'crime': 80,
    'mystery': 9648,
    'history': 36,
    'war': 10752,
    'music': 10402,
    'western': 37
}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)

# ===== Database helpers =====
def load_data():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def generate_thumbnail(video_path, video_id):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", video_path],
            capture_output=True, text=True, timeout=10
        )
        duration = float(result.stdout.strip()) if result.stdout.strip() else 0
        if duration <= 0:
            return None
        extraction_time = min(10, duration / 2)
        output_file = os.path.join(THUMBNAIL_FOLDER, f"{video_id}.jpg")
        cmd = [
            "ffmpeg", "-y", "-ss", str(extraction_time), "-i", video_path,
            "-vframes", "1", "-q:v", "2", output_file
        ]
        subprocess.run(cmd, check=True, timeout=30, capture_output=True)
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            return f"/thumbnails/{video_id}.jpg"
    except Exception as e:
        app.logger.error(f"Thumbnail generation failed for {video_path}: {e}")
    return None

def scan_folder_and_sync():
    data = load_data()
    existing_filenames = {v.get("filename") for v in data.get("videos", []) if v.get("filename")}
    added = 0
    for root, dirs, files in os.walk(VIDEO_FOLDER):
        for file in files:
            if file.rsplit('.', 1)[-1].lower() not in ALLOWED_EXTENSIONS:
                continue
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, VIDEO_FOLDER).replace('\\', '/')
            if rel_path in existing_filenames:
                continue
            video_id = str(uuid.uuid4())
            thumb_url = generate_thumbnail(full_path, video_id)
            new_video = {
                "id": video_id,
                "title": os.path.splitext(file)[0],
                "filename": rel_path,
                "category": "uncategorized",
                "description": "",
                "duration": "",
                "featured": False,
                "poster": "",
                "thumbnail": thumb_url or "",
                "status": "approved",
                "uploaded_at": datetime.utcnow().isoformat(),
                "user_id": "admin",
                "reason": ""
            }
            try:
                result = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", full_path],
                    capture_output=True, text=True, timeout=10
                )
                dur = float(result.stdout.strip()) if result.stdout.strip() else 0
                if dur:
                    new_video["duration"] = f"{int(dur//60)}:{int(dur%60):02d}"
            except:
                pass
            data.setdefault("videos", []).append(new_video)
            existing_filenames.add(rel_path)
            added += 1
    save_data(data)
    return added

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ===== TMDB Helpers =====
def tmdb_request(endpoint, params=None):
    url = f"{TMDB_BASE_URL}/{endpoint}"
    headers = {
        'Authorization': f'Bearer {TMDB_ACCESS_TOKEN}',
        'accept': 'application/json'
    }
    response = requests.get(url, headers=headers, params=params)
    return response.json()

def get_tmdb_movie(tmdb_id):
    return tmdb_request(f'movie/{tmdb_id}', {'language': 'en-US'})

def search_tmdb_movies(query, page=1):
    params = {'query': query, 'language': 'en-US', 'page': page}
    return tmdb_request('search/movie', params)

def get_tmdb_movies_by_category(category, page=1):
    endpoints = {
        'popular': 'movie/popular',
        'now_playing': 'movie/now_playing',
        'top_rated': 'movie/top_rated',
        'upcoming': 'movie/upcoming'
    }
    endpoint = endpoints.get(category)
    if endpoint:
        return tmdb_request(endpoint, {'language': 'en-US', 'page': page})
    genre_id = GENRE_MAP.get(category)
    if genre_id:
        return tmdb_request('discover/movie', {
            'language': 'en-US',
            'page': page,
            'with_genres': genre_id,
            'sort_by': 'popularity.desc'
        })
    return tmdb_request('movie/popular', {'language': 'en-US', 'page': page})

def get_tmdb_tv_show(tmdb_id):
    return tmdb_request(f'tv/{tmdb_id}', {'language': 'en-US'})

def search_tmdb_tv(query, page=1):
    params = {'query': query, 'language': 'en-US', 'page': page}
    return tmdb_request('search/tv', params)

def get_tmdb_tv_by_category(category, page=1):
    endpoints = {
        'popular': 'tv/popular',
        'top_rated': 'tv/top_rated',
        'on_the_air': 'tv/on_the_air',
        'airing_today': 'tv/airing_today'
    }
    endpoint = endpoints.get(category)
    if endpoint:
        return tmdb_request(endpoint, {'language': 'en-US', 'page': page})
    genre_id = GENRE_MAP.get(category)
    if genre_id:
        return tmdb_request('discover/tv', {
            'language': 'en-US',
            'page': page,
            'with_genres': genre_id,
            'sort_by': 'popularity.desc'
        })
    return tmdb_request('tv/popular', {'language': 'en-US', 'page': page})

def get_tmdb_tv_season(tmdb_id, season_num):
    return tmdb_request(f'tv/{tmdb_id}/season/{season_num}', {'language': 'en-US'})

def get_tmdb_movie_by_position(position=1):
    data = tmdb_request('movie/top_rated', {'language': 'en-US', 'page': 1})
    results = data.get('results', [])
    if results and position <= len(results):
        movie_id = results[position - 1]['id']
        return get_tmdb_movie(movie_id)
    return None

def get_tmdb_tv_by_position(position=1):
    data = tmdb_request('tv/top_rated', {'language': 'en-US', 'page': 1})
    results = data.get('results', [])
    if results and position <= len(results):
        show_id = results[position - 1]['id']
        return get_tmdb_tv_show(show_id)
    return None

# ===== SERVER URL HELPERS =====

# Server 2: Vidsrc URLs
def get_vidsrc_url(tmdb_id, media_type='movie', imdb_id=None, season=None, episode=None):
    if media_type == 'tv' and season and episode:
        primary = f"https://vidsrc.mov/embed/tv/{tmdb_id}/{season}/{episode}"
        alternates = []
        for domain in VIDSRC_DOMAINS[1:]:
            if domain != 'vidsrc.mov':
                alternates.append(f"https://{domain}/embed/tv/{tmdb_id}/{season}/{episode}")
        return {'primary': primary, 'alternates': alternates}
    
    if imdb_id:
        primary = f"https://vidsrc.mov/embed/{media_type}/{imdb_id}"
    else:
        primary = f"https://vidsrc.mov/embed/{media_type}/{tmdb_id}"
    
    alternates = []
    for domain in VIDSRC_DOMAINS[1:]:
        if domain != 'vidsrc.mov':
            if imdb_id:
                alternates.append(f"https://{domain}/embed/{media_type}/{imdb_id}")
            alternates.append(f"https://{domain}/embed/{media_type}/{tmdb_id}")
    
    return {'primary': primary, 'alternates': alternates}

# Server 1: SuperEmbed URLs (Recommended)
def get_superembed_url(tmdb_id, media_type='movie', imdb_id=None, season=None, episode=None, use_vip=False):
    """
    Get SuperEmbed URL (Server 1 - Recommended)
    """
    base_url = SUPEREMBED_SERVERS.get('vip' if use_vip else 'primary')
    
    if media_type == 'tv' and season and episode:
        if imdb_id:
            # Use IMDB ID if available
            tmdb_param = f"video_id={imdb_id}&s={season}&e={episode}"
        else:
            tmdb_param = f"video_id={tmdb_id}&tmdb=1&s={season}&e={episode}"
    else:
        if imdb_id:
            tmdb_param = f"video_id={imdb_id}"
        else:
            tmdb_param = f"video_id={tmdb_id}&tmdb=1"
    
    url = f"{base_url}?{tmdb_param}"
    return url

def get_all_servers(tmdb_id, media_type='movie', imdb_id=None, season=None, episode=None):
    """
    Get all available server URLs (Server 1: SuperEmbed, Server 2: Vidsrc)
    """
    servers = {
        'server1': {
            'name': 'SuperEmbed (Recommended)',
            'url': get_superembed_url(tmdb_id, media_type, imdb_id, season, episode, use_vip=False),
            'vip_url': get_superembed_url(tmdb_id, media_type, imdb_id, season, episode, use_vip=True),
            'type': 'superembed',
            'recommended': True
        }
    }
    
    # Add Vidsrc as Server 2
    vidsrc_urls = get_vidsrc_url(tmdb_id, media_type, imdb_id, season, episode)
    servers['server2'] = {
        'name': 'Vidsrc (Server 2)',
        'url': vidsrc_urls.get('primary'),
        'alternates': vidsrc_urls.get('alternates', []),
        'type': 'vidsrc',
        'recommended': False
    }
    
    return servers

# ===== Admin authorization =====
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# ===== YouTube helpers =====
def extract_youtube_id(url_or_id):
    patterns = [
        r"(?:youtube\.com\/watch\?v=|youtu\.be\/)([\w\-]+)",
        r"youtube\.com\/embed\/([\w\-]+)",
        r"^([\w\-]{11})$"
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    return None

def fetch_youtube_title(video_id):
    try:
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data.get('title', video_id)
    except Exception:
        pass
    return video_id

# ===== Public Routes =====

@app.route("/")
def index():
    data = load_data()
    site_config = data.get("site", {})
    return render_template("index.html", site=site_config)

# Add this route to serve static files like sitelogo.jpg
@app.route('/sitelogo.jpg')
def serve_logo():
    return send_from_directory('.', 'sitelogo.jpg')

# Also add a general static file route if needed
@app.route('/<path:filename>')
def serve_static_file(filename):
    # Only serve specific file types to avoid security issues
    if filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.css', '.js')):
        return send_from_directory('.', filename)
    return jsonify({'error': 'Not found'}), 404

@app.route("/movies")
def movies_page():
    return render_template("movies.html")

@app.route("/tvshows")
def tvshows_page():
    return render_template("tvshows.html")

@app.route("/about")
def about_page():
    data = load_data()
    site_config = data.get("site", {})
    about_config = site_config.get("aboutPage", {})
    return render_template("about.html", about=about_config, site=site_config)

@app.route("/contact")
def contact_page():
    data = load_data()
    site_config = data.get("site", {})
    contact_config = site_config.get("contactPage", {})
    return render_template("contact.html", contact=contact_config, site=site_config)

@app.route("/api/config")
def api_config():
    data = load_data()
    return jsonify(data.get("site", {}))

@app.route("/api/videos")
def api_videos():
    data = load_data()
    videos = []
    for v in data.get("videos", []):
        status = v.get("status")
        if status is None or status == "approved":
            if v.get("youtube_id"):
                v["src"] = f"https://www.youtube.com/embed/{v['youtube_id']}"
            elif v.get("filename"):
                v["src"] = f"/videos/{v['filename']}"
            else:
                v["src"] = None
            if not v.get("poster") or v["poster"].startswith("https://picsum"):
                v["poster"] = v.get("thumbnail") or f"https://picsum.photos/seed/{v['title'].replace(' ', '')}/400/225"
            v["posterLarge"] = v.get("thumbnail") or v["poster"]
            videos.append(v)
    return jsonify(videos)

@app.route("/videos/<path:filename>")
def serve_video(filename):
    return send_from_directory(VIDEO_FOLDER, filename)

@app.route("/thumbnails/<path:filename>")
def serve_thumbnail(filename):
    return send_from_directory(THUMBNAIL_FOLDER, filename)

# ===== TMDB Movie Routes =====

@app.route("/api/tmdb/movies/search")
def api_tmdb_search_movies():
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    if not query:
        return jsonify({'error': 'Query parameter required'}), 400
    
    try:
        data = search_tmdb_movies(query, page)
        for movie in data.get('results', []):
            # Add both server options
            movie['servers'] = get_all_servers(movie['id'], 'movie', movie.get('imdb_id'))
            movie['embed_urls'] = get_vidsrc_url(movie['id'], 'movie', movie.get('imdb_id'))  # Keep for backward compatibility
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/tmdb/movies/<category>")
def api_tmdb_movies_by_category(category):
    page = request.args.get('page', 1, type=int)
    try:
        data = get_tmdb_movies_by_category(category, page)
        for movie in data.get('results', []):
            movie['servers'] = get_all_servers(movie['id'], 'movie', movie.get('imdb_id'))
            movie['embed_urls'] = get_vidsrc_url(movie['id'], 'movie', movie.get('imdb_id'))
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/tmdb/movie/<int:tmdb_id>")
def api_tmdb_movie_detail(tmdb_id):
    try:
        data = get_tmdb_movie(tmdb_id)
        data['servers'] = get_all_servers(tmdb_id, 'movie', data.get('imdb_id'))
        data['embed_urls'] = get_vidsrc_url(tmdb_id, 'movie', data.get('imdb_id'))
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/tmdb/hero/play")
def api_tmdb_hero_play():
    data = load_data()
    site_config = data.get("site", {})
    hero_config = site_config.get("heroBanner", {})
    
    if not hero_config.get("enabled", True):
        return jsonify({"error": "Hero not enabled"}), 404
    
    media_type = hero_config.get("mediaType", "movie")
    position = hero_config.get("position", 1)
    
    try:
        if media_type == "movie":
            movie = get_tmdb_movie_by_position(position)
            if movie:
                imdb_id = movie.get('imdb_id')
                embed_urls = get_vidsrc_url(movie['id'], 'movie', imdb_id)
                return jsonify({
                    "id": movie.get('id'),
                    "title": movie.get('title'),
                    "imdb_id": imdb_id,
                    "media_type": "movie",
                    "embed_url": embed_urls.get('primary'),
                    "embed_urls": embed_urls
                })
        else:
            show = get_tmdb_tv_by_position(position)
            if show:
                return jsonify({
                    "id": show.get('id'),
                    "title": show.get('name'),
                    "media_type": "tv",
                    "first_air_date": show.get('first_air_date'),
                    "embed_url": None,
                })
    except Exception as e:
        app.logger.error(f"Hero play fetch error: {e}")
    
    return jsonify({"error": "Content not found"}), 404

@app.route("/api/tmdb/movie/<int:tmdb_id>/recommendations")
def api_tmdb_movie_recommendations(tmdb_id):
    try:
        data = tmdb_request(f'movie/{tmdb_id}/recommendations', {'language': 'en-US', 'page': 1})
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/tmdb/tv/<int:tmdb_id>/recommendations")
def api_tmdb_tv_recommendations(tmdb_id):
    try:
        data = tmdb_request(f'tv/{tmdb_id}/recommendations', {'language': 'en-US', 'page': 1})
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/tmdb/tv/<int:tmdb_id>/season/<int:season_num>")
def api_tmdb_tv_season_detail(tmdb_id, season_num):
    try:
        data = get_tmdb_tv_season(tmdb_id, season_num)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/tmdb/hero")
def api_tmdb_hero():
    data = load_data()
    site_config = data.get("site", {})
    hero_config = site_config.get("heroBanner", {})
    
    if not hero_config.get("enabled", True):
        return jsonify({
            "title": site_config.get("heroTitle", "Watch What Matters"),
            "overview": site_config.get("heroSubtitle", "A modern home for your media."),
            "poster_path": None,
            "backdrop_path": None,
            "media_type": None,
            "id": None
        })
    
    media_type = hero_config.get("mediaType", "movie")
    position = hero_config.get("position", 1)
    
    try:
        if media_type == "movie":
            movie = get_tmdb_movie_by_position(position)
            if movie:
                return jsonify({
                    "id": movie.get('id'),
                    "title": movie.get('title'),
                    "overview": movie.get('overview', ''),
                    "poster_path": movie.get('poster_path'),
                    "backdrop_path": movie.get('backdrop_path'),
                    "vote_average": movie.get('vote_average'),
                    "release_date": movie.get('release_date'),
                    "media_type": "movie"
                })
        else:
            show = get_tmdb_tv_by_position(position)
            if show:
                return jsonify({
                    "id": show.get('id'),
                    "title": show.get('name'),
                    "overview": show.get('overview', ''),
                    "poster_path": show.get('poster_path'),
                    "backdrop_path": show.get('backdrop_path'),
                    "vote_average": show.get('vote_average'),
                    "first_air_date": show.get('first_air_date'),
                    "media_type": "tv"
                })
    except Exception as e:
        app.logger.error(f"Hero fetch error: {e}")
    
    return jsonify({
        "title": site_config.get("heroTitle", "Watch What Matters"),
        "overview": site_config.get("heroSubtitle", "A modern home for your media."),
        "poster_path": None,
        "backdrop_path": hero_config.get("fallbackImage"),
        "media_type": None,
        "id": None
    })

# ===== TMDB TV Show Routes =====

@app.route("/api/tmdb/tv/search")
def api_tmdb_search_tv():
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    if not query:
        return jsonify({'error': 'Query parameter required'}), 400
    
    try:
        data = search_tmdb_tv(query, page)
        # Add server info for TV shows too
        for show in data.get('results', []):
            show['servers'] = get_all_servers(show['id'], 'tv')
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/tmdb/tv/<category>")
def api_tmdb_tv_by_category(category):
    page = request.args.get('page', 1, type=int)
    try:
        data = get_tmdb_tv_by_category(category, page)
        for show in data.get('results', []):
            show['servers'] = get_all_servers(show['id'], 'tv')
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/tmdb/tv/<int:tmdb_id>")
def api_tmdb_tv_detail(tmdb_id):
    try:
        data = get_tmdb_tv_show(tmdb_id)
        data['servers'] = get_all_servers(tmdb_id, 'tv')
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/tmdb/tv/<int:tmdb_id>/season/<int:season_num>")
def api_tmdb_tv_season(tmdb_id, season_num):
    try:
        data = get_tmdb_tv_season(tmdb_id, season_num)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/tmdb/tv/play/<int:tmdb_id>/<int:season>/<int:episode>")
def api_tmdb_tv_play(tmdb_id, season, episode):
    try:
        servers = get_all_servers(tmdb_id, 'tv', season=season, episode=episode)
        return jsonify(servers)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/servers/<int:tmdb_id>/<media_type>")
def api_get_servers(tmdb_id, media_type):
    """Get all available server URLs for a movie or TV show"""
    try:
        imdb_id = request.args.get('imdb_id')
        season = request.args.get('season', type=int)
        episode = request.args.get('episode', type=int)
        
        servers = get_all_servers(tmdb_id, media_type, imdb_id, season, episode)
        return jsonify(servers)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== Player page =====
@app.route("/player/<video_id>")
def player_page(video_id):
    data = load_data()
    video = next((v for v in data.get("videos", []) if v.get("id") == video_id), None)
    if not video:
        return render_template("error.html", message="Video not found"), 404
    return render_template("player.html", video=video)

@app.route("/api/video/<video_id>")
def api_video_detail(video_id):
    data = load_data()
    for v in data.get("videos", []):
        if v.get("id") == video_id:
            if v.get("status") not in (None, "approved"):
                return jsonify({"error": "Video not available"}), 404
            if v.get("youtube_id"):
                v["src"] = f"https://www.youtube.com/embed/{v['youtube_id']}"
            elif v.get("filename"):
                v["src"] = f"/videos/{v['filename']}"
            else:
                v["src"] = None
            if not v.get("poster") or v["poster"].startswith("https://picsum"):
                v["poster"] = v.get("thumbnail") or f"https://picsum.photos/seed/{v['title'].replace(' ', '')}/400/225"
            v["posterLarge"] = v.get("thumbnail") or v["poster"]
            return jsonify(v)
    return jsonify({"error": "Video not found"}), 404

# ===== Upload endpoint =====
@app.route("/api/upload", methods=["POST"])
def upload_video():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type"}), 400

    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(UPLOAD_FOLDER, unique_name)
    file.save(save_path)

    duration = 0
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", save_path],
            capture_output=True, text=True, timeout=10
        )
        duration = float(result.stdout.strip()) if result.stdout.strip() else 0
        if duration > MAX_DURATION_SEC:
            os.remove(save_path)
            return jsonify({"error": "Video exceeds 20 hours limit"}), 400
    except FileNotFoundError:
        app.logger.warning("ffprobe not found – skipping duration check")
    except Exception as e:
        app.logger.error(f"Duration check error: {e}")
        os.remove(save_path)
        return jsonify({"error": "Unable to read video duration"}), 400

    video_id = unique_name.rsplit('.', 1)[0]
    thumbnail_url = generate_thumbnail(save_path, video_id)
    if not thumbnail_url:
        thumbnail_url = "/static/fallback_thumbnail.jpg"

    data = load_data()
    new_video = {
        "id": video_id,
        "title": file.filename.rsplit('.', 1)[0],
        "filename": f"uploads/{unique_name}",
        "category": "uncategorized",
        "description": "",
        "duration": f"{int(duration//60)}:{int(duration%60):02d}" if duration else "",
        "featured": False,
        "poster": "",
        "thumbnail": thumbnail_url,
        "status": "pending",
        "uploaded_at": datetime.utcnow().isoformat(),
        "user_id": "anonymous",
        "reason": ""
    }
    data["videos"].append(new_video)
    save_data(data)
    return jsonify({"message": "Upload successful! Video pending approval.", "video": new_video}), 201

# ===== Admin routes =====
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        return render_template("admin_login.html", error="Invalid password")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.route("/admin")
@admin_required
def admin_dashboard():
    data = load_data()
    all_videos = data.get("videos", [])
    return render_template("admin.html", videos=all_videos)

@app.route("/admin/approve/<video_id>", methods=["POST"])
@admin_required
def approve_video(video_id):
    data = load_data()
    for v in data["videos"]:
        if v["id"] == video_id:
            v["status"] = "approved"
            save_data(data)
            return jsonify({"message": "Video approved"})
    return jsonify({"error": "Video not found"}), 404

@app.route("/admin/reject/<video_id>", methods=["POST"])
@admin_required
def reject_video(video_id):
    reason = request.form.get("reason", "")
    data = load_data()
    for v in data["videos"]:
        if v["id"] == video_id:
            v["status"] = "rejected"
            v["reason"] = reason
            save_data(data)
            return jsonify({"message": "Video rejected"})
    return jsonify({"error": "Video not found"}), 404

@app.route("/admin/hide/<video_id>", methods=["POST"])
@admin_required
def hide_video(video_id):
    data = load_data()
    for v in data["videos"]:
        if v["id"] == video_id:
            v["status"] = "hidden"
            save_data(data)
            return jsonify({"message": "Video hidden"})
    return jsonify({"error": "Video not found"}), 404

@app.route("/admin/delete/<video_id>", methods=["POST"])
@admin_required
def delete_video(video_id):
    data = load_data()
    video = next((v for v in data["videos"] if v["id"] == video_id), None)
    if not video:
        return jsonify({"error": "Video not found"}), 404

    if video.get("filename"):
        video_path = os.path.join(VIDEO_FOLDER, video["filename"])
        if os.path.exists(video_path):
            try:
                os.remove(video_path)
            except Exception as e:
                app.logger.error(f"Failed to delete video file: {e}")

    if video.get("thumbnail"):
        thumb_filename = os.path.basename(video["thumbnail"].split('?')[0])
        thumb_path = os.path.join(THUMBNAIL_FOLDER, thumb_filename)
        if os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
            except Exception as e:
                app.logger.error(f"Failed to delete thumbnail: {e}")

    data["videos"] = [v for v in data["videos"] if v["id"] != video_id]
    save_data(data)
    return jsonify({"message": "Video deleted permanently"})

@app.route("/admin/regenerate-thumbnail/<video_id>", methods=["POST"])
@admin_required
def regenerate_single_thumbnail(video_id):
    data = load_data()
    for v in data["videos"]:
        if v["id"] == video_id:
            if not v.get("filename"):
                return jsonify({"error": "YouTube videos don't have local thumbnails"}), 400
            file_path = os.path.join(VIDEO_FOLDER, v["filename"])
            if not os.path.exists(file_path):
                return jsonify({"error": "Video file not found"}), 404
            thumb_url = generate_thumbnail(file_path, video_id)
            if thumb_url:
                v["thumbnail"] = thumb_url
                v["poster"] = thumb_url
                save_data(data)
                return jsonify({"message": "Thumbnail regenerated"})
            return jsonify({"error": "Thumbnail generation failed"}), 500
    return jsonify({"error": "Video not found"}), 404

@app.route("/admin/generate-thumbnails", methods=["POST"])
@admin_required
def regenerate_all_thumbnails():
    data = load_data()
    updated = 0
    for v in data["videos"]:
        if v.get("filename") and (not v.get("poster") or v["poster"].startswith("https://picsum")):
            file_path = os.path.join(VIDEO_FOLDER, v["filename"])
            if os.path.exists(file_path):
                thumb_url = generate_thumbnail(file_path, v["id"])
                if thumb_url:
                    v["thumbnail"] = thumb_url
                    v["poster"] = thumb_url
                    updated += 1
    save_data(data)
    return jsonify({"message": f"Thumbnails regenerated for {updated} videos"})

@app.route("/admin/scan-folder", methods=["POST"])
@admin_required
def scan_folder():
    added = scan_folder_and_sync()
    return jsonify({"message": f"Scan complete. Added {added} new video(s)."})

@app.route("/admin/add-youtube", methods=["GET", "POST"])
@admin_required
def add_youtube():
    if request.method == "POST":
        video_type = request.form.get("video_type", "single")

        if video_type == "single":
            url_or_id = request.form.get("youtube_url", "").strip()
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            category = request.form.get("category", "uncategorized").strip()
            if not category:
                category = "uncategorized"

            video_id = extract_youtube_id(url_or_id)
            if not video_id:
                flash("Invalid YouTube URL or ID", "danger")
                return redirect(url_for("add_youtube"))

            if not title:
                title = fetch_youtube_title(video_id)

            new_video = {
                "id": str(uuid.uuid4()),
                "youtube_id": video_id,
                "title": title,
                "description": description,
                "duration": "",
                "category": category,
                "featured": False,
                "thumbnail": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                "poster": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                "status": "approved",
                "uploaded_at": datetime.utcnow().isoformat(),
                "user_id": "admin",
                "reason": "",
            }
            data = load_data()
            data.setdefault("videos", []).append(new_video)
            save_data(data)
            flash(f"YouTube video '{title}' added successfully!", "success")

        elif video_type == "tv":
            show_title = request.form.get("show_title", "").strip()
            if not show_title:
                flash("Show title is required", "danger")
                return redirect(url_for("add_youtube"))
            category = request.form.get("category", "uncategorized").strip()
            description = request.form.get("description", "").strip()

            seasons_data = {}
            for key, value in request.form.items():
                if key.startswith("season_"):
                    parts = key.split("_")
                    if len(parts) >= 5:
                        try:
                            season_num = int(parts[1])
                            ep_num = int(parts[3])
                            field_type = parts[4]
                            if season_num not in seasons_data:
                                seasons_data[season_num] = {"episodes": {}}
                            if ep_num not in seasons_data[season_num]["episodes"]:
                                seasons_data[season_num]["episodes"][ep_num] = {}
                            seasons_data[season_num]["episodes"][ep_num][field_type] = value.strip()
                        except (ValueError, IndexError):
                            continue

            if not seasons_data:
                flash("No episodes provided", "danger")
                return redirect(url_for("add_youtube"))

            seasons_list = []
            for season_num in sorted(seasons_data.keys()):
                episodes_dict = seasons_data[season_num]["episodes"]
                episodes_list = []
                for ep_num in sorted(episodes_dict.keys()):
                    ep = episodes_dict[ep_num]
                    youtube_id = extract_youtube_id(ep.get("url", ""))
                    if not youtube_id:
                        flash(f"Invalid YouTube URL for Season {season_num}, Episode {ep_num}", "danger")
                        return redirect(url_for("add_youtube"))
                    episodes_list.append({
                        "episode": ep_num,
                        "title": ep.get("title", f"Episode {ep_num}"),
                        "youtube_id": youtube_id,
                        "duration": "",
                        "description": ep.get("desc", ""),
                    })
                seasons_list.append({
                    "season": season_num,
                    "episodes": episodes_list
                })

            show_id = str(uuid.uuid4())
            first_ep = seasons_list[0]["episodes"][0]
            poster_url = f"https://img.youtube.com/vi/{first_ep['youtube_id']}/mqdefault.jpg"
            new_show = {
                "id": show_id,
                "title": show_title,
                "description": description,
                "category": category,
                "featured": False,
                "thumbnail": poster_url,
                "poster": poster_url,
                "status": "approved",
                "uploaded_at": datetime.utcnow().isoformat(),
                "user_id": "admin",
                "seasons": seasons_list,
            }
            data = load_data()
            data.setdefault("videos", []).append(new_show)
            save_data(data)
            flash(f"TV Show '{show_title}' with {sum(len(s['episodes']) for s in seasons_list)} episodes added!", "success")

        return redirect(url_for("admin_dashboard"))

    return render_template("add_youtube.html")

@app.route("/static/fallback_thumbnail.jpg")
def fallback_thumbnail():
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (400, 225), color=(26, 26, 37))
    d = ImageDraw.Draw(img)
    d.text((150, 100), "Mariow", fill=(232, 69, 107))
    img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "fallback_thumbnail.jpg")
    os.makedirs(os.path.dirname(img_path), exist_ok=True)
    img.save(img_path)
    return send_from_directory(os.path.dirname(img_path), "fallback_thumbnail.jpg")

with app.app_context():
    added_on_startup = scan_folder_and_sync()
    app.logger.info(f"Startup scan: added {added_on_startup} new videos.")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=6868)