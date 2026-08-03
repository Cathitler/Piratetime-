import socket
import requests
import json
from urllib.parse import urlparse

def get_ip_and_location(domain):
    """
    Get IP address and location information for a domain
    """
    try:
        # Get IP address
        ip_address = socket.gethostbyname(domain)
        print(f"Domain: {domain}")
        print(f"IP Address: {ip_address}")
        print("-" * 40)
        
        # Get location information using ip-api.com (free, no API key needed)
        response = requests.get(f'http://ip-api.com/json/{ip_address}')
        location_data = response.json()
        
        if location_data['status'] == 'success':
            print("\n📍 LOCATION INFORMATION:")
            print(f"Country: {location_data['country']} ({location_data['countryCode']})")
            print(f"Region: {location_data['regionName']}")
            print(f"City: {location_data['city']}")
            print(f"ISP: {location_data['isp']}")
            print(f"Organization: {location_data['org']}")
            print(f"AS: {location_data['as']}")
            print(f"Latitude: {location_data['lat']}")
            print(f"Longitude: {location_data['lon']}")
            print(f"Timezone: {location_data['timezone']}")
            print(f"ZIP Code: {location_data['zip']}")
        else:
            print("❌ Could not fetch location data")
            print(f"Status: {location_data.get('message', 'Unknown error')}")
            
        return ip_address, location_data
        
    except socket.gaierror:
        print(f"❌ Error: Could not resolve domain '{domain}'")
        return None, None
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching location data: {e}")
        return None, None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None, None

# Extract domain from URL
url = "https://outlawtv.loophole.site/"
parsed_url = urlparse(url)
domain = parsed_url.hostname  # This will give "pool.hashvault.pro"

print("=" * 50)
print(f"Analyzing URL: {url}")
print("=" * 50)

# Get IP and location
ip, location = get_ip_and_location(domain)

# Additional information
if ip:
    print("\n🔍 ADDITIONAL INFO:")
    print(f"Port: {parsed_url.port or 80}")
    print(f"Protocol: {parsed_url.scheme}")
    print(f"Full URL: {url}")