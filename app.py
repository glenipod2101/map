from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import pandas as pd
from geopy.geocoders import GoogleV3
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time
import folium
from folium.plugins import MarkerCluster
import os
import uuid

from dotenv import load_dotenv


load_dotenv()


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAP_FOLDER'] = 'maps'
app.config['GEOCODED_FOLDER'] = 'geocoded'

# Create the upload, map, and geocoded folders if they don't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['MAP_FOLDER'], exist_ok=True) 
os.makedirs(app.config['GEOCODED_FOLDER'], exist_ok=True)

# Your Google Maps API key
GM_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download/map/<filename>')
def download_map(filename):
    response = send_from_directory(app.config['MAP_FOLDER'], filename, as_attachment=True)
    # Set headers to force download
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-Type"] = "text/html"
    return response


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(url_for('index'))
    
    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('index'))
    
    # Generate a unique filename
    unique_id = str(uuid.uuid4())
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_id}.csv")
    file.save(file_path)
    
    # Read the CSV to get column names
    try:
        df = pd.read_csv(file_path)
        columns = df.columns.tolist()
        return render_template('select_columns.html', 
                               columns=columns, 
                               file_path=file_path)
    except Exception as e:
        return f"Error reading CSV: {str(e)}"

@app.route('/process', methods=['POST'])
def process_file():
    file_path = request.form['file_path']
    origin_column = request.form['origin_column']
    destination_column = request.form['destination_column']
    
    # Generate unique IDs for the output files
    unique_id = os.path.basename(file_path).split('.')[0]
    geocoded_path = os.path.join(app.config['GEOCODED_FOLDER'], f"geocoded_{unique_id}.csv")
    map_path = os.path.join(app.config['MAP_FOLDER'], f"map_{unique_id}.html")
    
    # Run the geocoding and mapping process
    try:
        create_map(file_path, origin_column, destination_column, geocoded_path, map_path)
        return render_template('result.html', map_file=f"map_{unique_id}.html")
    except Exception as e:
        return f"Error creating map: {str(e)}"

@app.route('/maps/<filename>')
def get_map(filename):
    return send_from_directory(app.config['MAP_FOLDER'], filename)

@app.route('/geocoded/<filename>')
def download_geocoded(filename):
    return send_from_directory(app.config['GEOCODED_FOLDER'], filename)

def get_lat_long(address, retries=3):
    """Get latitude and longitude from address with retry logic"""
    # Initialize the geocoder
    geolocator = GoogleV3(api_key=GM_API_KEY)
    
    # Add USA to make sure we get US zipcodes
    if address and len(str(address).strip()) <= 10:  # Likely a zipcode
        address = f"{address}, USA"
    
    for attempt in range(retries):
        try:
            location = geolocator.geocode(address)
            if location:
                return (location.latitude, location.longitude)
            else:
                print(f"Address '{address}' could not be geocoded.")
                return None
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"Error geocoding address '{address}': {e}")
            if attempt < retries - 1:
                time.sleep(2)  # Wait before retrying
            else:
                return None

def create_map(file_path, origin_column, destination_column, geocoded_path, map_path):
    """Create a map from the CSV file"""
    # Read the CSV file
    df = pd.read_csv(file_path)
    print(f"Successfully loaded CSV with {len(df)} rows")
    
    # Verify the columns exist
    if origin_column not in df.columns:
        raise ValueError(f"Column '{origin_column}' not found in CSV")
    
    if destination_column not in df.columns:
        raise ValueError(f"Column '{destination_column}' not found in CSV")
    
    # Add unique ID to each row if not already present
    if 'ID' not in df.columns:
        df['ID'] = df.index + 1
    
    # Add new columns for latitude and longitude
    df['Origin_Latitude'] = None
    df['Origin_Longitude'] = None
    df['Destination_Latitude'] = None
    df['Destination_Longitude'] = None
    
    # Create dictionaries to cache geocoded results to avoid duplicate API calls
    origin_cache = {}
    dest_cache = {}
    
    # Sample code for testing with small datasets - remove for production
    # Uncomment to test with fewer rows
    # df = df.head(10)
    
    print("Starting geocoding process...")
    for index, row in df.iterrows():
        try:
            # Geocode the origin address
            origin_address = str(row[origin_column]).strip()
            if origin_address in origin_cache:
                # Use cached result
                origin_location = origin_cache[origin_address]
            else:
                # Geocode and cache result
                print(f"Geocoding origin ({index+1}/{len(df)}): {origin_address}")
                origin_location = get_lat_long(origin_address)
                origin_cache[origin_address] = origin_location
            
            if origin_location is not None:
                df.at[index, 'Origin_Latitude'] = origin_location[0]
                df.at[index, 'Origin_Longitude'] = origin_location[1]
            
            # Geocode the destination address
            dest_address = str(row[destination_column]).strip()
            if dest_address in dest_cache:
                # Use cached result
                dest_location = dest_cache[dest_address]
            else:
                # Geocode and cache result
                print(f"Geocoding destination ({index+1}/{len(df)}): {dest_address}")
                dest_location = get_lat_long(dest_address)
                dest_cache[dest_address] = dest_location
            
            if dest_location is not None:
                df.at[index, 'Destination_Latitude'] = dest_location[0]
                df.at[index, 'Destination_Longitude'] = dest_location[1]
            
            # Add a small delay to avoid hitting API limits
            time.sleep(0.2)
            
        except Exception as e:
            print(f"Error processing row {index}: {e}")
    
    # Save the geocoded data
    df.to_csv(geocoded_path, index=False)
    print(f"Saved geocoded data to {geocoded_path}")
    
    # Remove rows with missing latitude or longitude values
    complete_data = df.dropna(subset=['Origin_Latitude', 'Origin_Longitude', 'Destination_Latitude', 'Destination_Longitude'])
    print(f"Found {len(complete_data)} rows with complete geocoding")
    
    if len(complete_data) == 0:
        raise ValueError("No complete geocoded entries found. Map cannot be created.")
    
    # Create a map centered around the continental US
    m = folium.Map(location=[39.8283, -98.5795], zoom_start=4)
    
    # Use MarkerClusters to handle many points
    origin_cluster = MarkerCluster(name="Origin Locations", show=True)
    dest_cluster = MarkerCluster(name="Destination Locations", show=True)
    
    # Create a feature group for lines that can be toggled
    lines = folium.FeatureGroup(name="Routes", show=False)
    
    # Count frequency of each location
    origin_counts = complete_data[origin_column].value_counts().to_dict()
    dest_counts = complete_data[destination_column].value_counts().to_dict()
    
    # Store unique locations to prevent duplicates
    unique_origins = {}
    unique_dests = {}
    
    # Add markers for origin and destination locations
    for index, row in complete_data.iterrows():
        id_value = row['ID']
        origin_address = str(row[origin_column])
        dest_address = str(row[destination_column])
        
        # Create popup content with frequency info
        origin_count = origin_counts.get(row[origin_column], 0)
        dest_count = dest_counts.get(row[destination_column], 0)
        
        origin_popup = f"<b>Origin:</b> {origin_address}<br><b>Frequency:</b> {origin_count} shipments"
        dest_popup = f"<b>Destination:</b> {dest_address}<br><b>Frequency:</b> {dest_count} shipments"
        
        # Get coordinates
        origin_coords = (row['Origin_Latitude'], row['Origin_Longitude'])
        dest_coords = (row['Destination_Latitude'], row['Destination_Longitude'])
        
        # Origin marker - check for duplicates
        origin_key = f"{origin_coords[0]:.6f},{origin_coords[1]:.6f}"
        if origin_key not in unique_origins:
            origin_marker = folium.Marker(
                location=origin_coords,
                popup=origin_popup,
                tooltip=f"Origin: {origin_address[:20]}..." if len(origin_address) > 20 else f"Origin: {origin_address}",
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
                tooltip=f"Destination: {dest_address[:20]}..." if len(dest_address) > 20 else f"Destination: {dest_address}",
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
            popup=f"From: {origin_address} To: {dest_address}"
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
        <h3 style="margin: 0;">Location Map</h3>
        <p style="margin: 5px 0 0 0;"><b>Blue</b>: Origin Locations</p>
        <p style="margin: 0;"><b>Red</b>: Destination Locations</p>
        <p style="margin: 0;">• Click markers to see details</p>
        <p style="margin: 0;">• Toggle layers using the control panel</p>
        <p style="margin: 0;">• Turn off Routes for better readability</p>
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))
    
    # Add Layer Control 
    folium.LayerControl().add_to(m)
    
    # Save the map
    m.save(map_path)
    print(f"Interactive map saved to {map_path}")
    
    return map_path

if __name__ == '__main__':
    app.run(debug=True)