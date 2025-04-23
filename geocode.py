import pandas as pd
from geopy.geocoders import GoogleV3
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time
import folium
from folium.plugins import MarkerCluster

# Your Google Maps API key
GM_API_KEY = 'AIzaSyDk6QAxrCRJ3M9vGUVoSOZFZopu9HRi6eQ'

# Initialize the geocoder with your API key
geolocator = GoogleV3(api_key=GM_API_KEY)

# Function to get latitude and longitude with retry logic
def get_lat_long(zipcode, retries=3):
    # Add USA to make sure we get US zipcodes
    address = f"{zipcode}, USA"
    for attempt in range(retries):
        try:
            location = geolocator.geocode(address)
            if location:
                return (location.latitude, location.longitude)
            else:
                print(f"Zipcode '{zipcode}' could not be geocoded.")
                return None
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"Error geocoding zipcode '{zipcode}': {e}")
            if attempt < retries - 1:
                time.sleep(2)  # Wait before retrying
            else:
                return None

# Read the CSV file
try:
    # Attempt to read the CSV - update this path to match your file location
    df = pd.read_csv('othermovingcompany.csv')
    print(f"Successfully loaded CSV with {len(df)} rows")
    print("Columns in the CSV:", df.columns.tolist())
except Exception as e:
    print(f"Error reading CSV file: {e}")
    # Fallback to example data if CSV reading fails
    df = pd.DataFrame({
        'From Zip': ['90210', '10001', '60601'],
        'To Zip': ['20001', '33101', '98101']
    })
    print("Using example data instead")

# Set the column names based on your CSV
origin_column = 'Moving From'
destination_column = 'Moving To Zip'

# Verify the columns exist
if origin_column not in df.columns:
    print(f"Column '{origin_column}' not found. Available columns: {df.columns.tolist()}")
    exit()

if destination_column not in df.columns:
    print(f"Column '{destination_column}' not found. Available columns: {df.columns.tolist()}")
    exit()

print(f"Using '{origin_column}' as the origin column")
print(f"Using '{destination_column}' as the destination column")

# Try to read from existing geocoded file first to avoid re-geocoding
try:
    geocoded_df = pd.read_csv('othermovingcompany.csv')
    print("Found existing geocoded data - using this instead of re-geocoding")
    
    # Check if it has the required columns
    required_cols = ['ID', 'Origin_Latitude', 'Origin_Longitude', 'Destination_Latitude', 'Destination_Longitude']
    if all(col in geocoded_df.columns for col in required_cols):
        df = geocoded_df
        geocoded = True
    else:
        print("Existing geocoded data missing required columns, will geocode again")
        geocoded = False
except Exception as e:
    print(f"No existing geocoded data found or error: {e}")
    geocoded = False

# Add unique ID to each row if not already present
if 'ID' not in df.columns:
    df['ID'] = df.index + 1

# Geocode the addresses if needed
if not geocoded:
    # Add new columns for latitude and longitude
    df['Origin_Latitude'] = None
    df['Origin_Longitude'] = None
    df['Destination_Latitude'] = None
    df['Destination_Longitude'] = None
    
    # Create dictionaries to cache geocoded results to avoid duplicate API calls
    origin_cache = {}
    dest_cache = {}
    
    print("Starting geocoding process...")
    for index, row in df.iterrows():
        try:
            # Geocode the origin zipcode
            origin_zip = str(row[origin_column]).strip()
            if origin_zip in origin_cache:
                # Use cached result
                origin_location = origin_cache[origin_zip]
                print(f"Using cached location for origin zipcode: {origin_zip}")
            else:
                # Geocode and cache result
                print(f"Geocoding origin ({index+1}/{len(df)}): {origin_zip}")
                origin_location = get_lat_long(origin_zip)
                origin_cache[origin_zip] = origin_location
            
            if origin_location is not None:
                df.at[index, 'Origin_Latitude'] = origin_location[0]
                df.at[index, 'Origin_Longitude'] = origin_location[1]
            
            # Geocode the destination zipcode
            dest_zip = str(row[destination_column]).strip()
            if dest_zip in dest_cache:
                # Use cached result
                dest_location = dest_cache[dest_zip]
                print(f"Using cached location for destination zipcode: {dest_zip}")
            else:
                # Geocode and cache result
                print(f"Geocoding destination ({index+1}/{len(df)}): {dest_zip}")
                dest_location = get_lat_long(dest_zip)
                dest_cache[dest_zip] = dest_location
            
            if dest_location is not None:
                df.at[index, 'Destination_Latitude'] = dest_location[0]
                df.at[index, 'Destination_Longitude'] = dest_location[1]
            
            # Add a small delay to avoid hitting API limits
            time.sleep(0.2)
            
            # Save progress every 50 rows
            if (index + 1) % 50 == 0:
                df.to_csv('geocoded_zipcodes_progress.csv', index=False)
                print(f"Progress saved at row {index+1}")
            
        except Exception as e:
            print(f"Error processing row {index}: {e}")
    
    # Save the geocoded data back to CSV
    geocoded_csv_path = 'geocoded_zipcodes.csv'
    df.to_csv(geocoded_csv_path, index=False)
    print(f"Saved geocoded data to {geocoded_csv_path}")

# Remove rows with missing latitude or longitude values
complete_data = df.dropna(subset=['Origin_Latitude', 'Origin_Longitude', 'Destination_Latitude', 'Destination_Longitude'])
print(f"Found {len(complete_data)} rows with complete geocoding")

if len(complete_data) == 0:
    print("No complete geocoded entries found. Map cannot be created.")
    exit()

# Create a map centered around the continental US
m = folium.Map(location=[39.8283, -98.5795], zoom_start=4)

# Use MarkerClusters to handle many points
origin_cluster = MarkerCluster(name="Origin Zip Codes", show=True)
dest_cluster = MarkerCluster(name="Destination Zip Codes", show=True)

# Create a feature group for lines that can be toggled
lines = folium.FeatureGroup(name="Routes (Toggle off to improve readability)")

# Count frequency of each zip code
origin_counts = complete_data[origin_column].value_counts().to_dict()
dest_counts = complete_data[destination_column].value_counts().to_dict()

# Store unique locations to prevent duplicates
unique_origins = {}
unique_dests = {}

# Add markers for origin and destination locations
for index, row in complete_data.iterrows():
    id_value = row['ID']
    origin_zip = str(row[origin_column])
    dest_zip = str(row[destination_column])
    
    # Create popup content with frequency info
    origin_count = origin_counts.get(row[origin_column], 0)
    dest_count = dest_counts.get(row[destination_column], 0)
    
    origin_popup = f"<b>Origin Zip:</b> {origin_zip}<br><b>Frequency:</b> {origin_count} shipments"
    dest_popup = f"<b>Destination Zip:</b> {dest_zip}<br><b>Frequency:</b> {dest_count} shipments"
    
    # Get coordinates
    origin_coords = (row['Origin_Latitude'], row['Origin_Longitude'])
    dest_coords = (row['Destination_Latitude'], row['Destination_Longitude'])
    
    # Origin marker - check for duplicates
    origin_key = f"{origin_coords[0]:.6f},{origin_coords[1]:.6f}"
    if origin_key not in unique_origins:
        origin_marker = folium.Marker(
            location=origin_coords,
            popup=origin_popup,
            tooltip=f"Origin: {origin_zip}",
            icon=folium.Icon(color='blue', icon='home')
        )
        origin_marker.add_to(origin_cluster)
        unique_origins[origin_key] = True
    
    # Destination marker - check for duplicates
    dest_key = f"{dest_coords[0]:.6f},{dest_coords[1]:.6f}"
    if dest_key not in unique_dests:
        dest_marker = folium.Marker(
            location=dest_coords,
            popup=dest_popup,
            tooltip=f"Destination: {dest_zip}",
            icon=folium.Icon(color='red', icon='flag')
        )
        dest_marker.add_to(dest_cluster)
        unique_dests[dest_key] = True
    
    # Add line connecting origin and destination (semi-transparent to reduce visual clutter)
    line = folium.PolyLine(
        locations=[origin_coords, dest_coords],
        color='green',
        weight=1,  # Thinner lines
        opacity=0.2,  # More transparent
        popup=f"From: {origin_zip} To: {dest_zip}"
    )
    line.add_to(lines)

# Add all components to the map
m.add_child(origin_cluster)
m.add_child(dest_cluster)
m.add_child(lines)

# Add a title and instructions to the map
title_html = """
<div style="position: fixed; 
            top: 10px; 
            left: 50px; 
            width: 300px;
            z-index: 9999; 
            background-color: white; 
            padding: 10px; 
            border-radius: 5px; 
            box-shadow: 0 0 10px rgba(0,0,0,0.5);">
    <h3 style="margin: 0;">Zip Code Map</h3>
    <p style="margin: 5px 0 0 0;"><b>Blue</b>: Origin Zip Codes</p>
    <p style="margin: 0;"><b>Red</b>: Destination Zip Codes</p>
    <p style="margin: 0;">• Click markers to see details</p>
    <p style="margin: 0;">• Toggle layers using the control panel</p>
    <p style="margin: 0;">• Turn off Routes for better readability</p>
</div>
"""
m.get_root().html.add_child(folium.Element(title_html))

# Add Layer Control 
folium.LayerControl().add_to(m)

# Save the map to an HTML file
map_file_path = 'zipcode_map.html'
m.save(map_file_path)
print(f"Interactive map saved to {map_file_path}")