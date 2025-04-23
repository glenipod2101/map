from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify
import csv
import io
from geopy.geocoders import GoogleV3
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time
import folium
from folium.plugins import MarkerCluster
import os
import uuid
import threading
from dotenv import load_dotenv
import multiprocessing

# Set Gunicorn timeout to a higher value
# This must be before the app is created
os.environ['GUNICORN_CMD_ARGS'] = "--timeout 120"

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
# Store background jobs
app.config['JOBS'] = {}
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAP_FOLDER'] = 'maps'
app.config['GEOCODED_FOLDER'] = 'geocoded'

# Create the upload, map, and geocoded folders if they don't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['MAP_FOLDER'], exist_ok=True) 
os.makedirs(app.config['GEOCODED_FOLDER'], exist_ok=True)

# Get API key from environment variable
GM_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY')
if not GM_API_KEY:
    print("WARNING: Google Maps API key not found in environment variables!")

@app.route('/')
def index():
    return render_template('index.html')

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
        columns = []
        with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            # First row contains headers
            headers = next(reader)
            columns = headers
            
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
    
    # Count rows in the file to determine if we need batch processing
    row_count = 0
    with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # Skip header
        for _ in reader:
            row_count += 1
    
    # If file is large, start processing in the background and show progress page
    if row_count > 30:  # More than 30 rows
        # Store job info
        job_id = str(uuid.uuid4())
        app.config['JOBS'][job_id] = {
            'status': 'processing',
            'progress': 0,
            'file_path': file_path,
            'origin_column': origin_column,
            'destination_column': destination_column,
            'geocoded_path': geocoded_path,
            'map_path': map_path,
            'unique_id': unique_id
        }
        
        # Start a background thread to process the data
        threading.Thread(
            target=process_in_background,
            args=(job_id, file_path, origin_column, destination_column, geocoded_path, map_path)
        ).start()
        
        # Return the processing page with job_id
        return render_template('processing.html', job_id=job_id)
    else:
        # For small files, process directly
        try:
            create_map(file_path, origin_column, destination_column, geocoded_path, map_path, max_rows=100)
            return render_template('result.html', map_file=f"map_{unique_id}.html")
        except Exception as e:
            return f"Error creating map: {str(e)}"
            
def process_in_background(job_id, file_path, origin_column, destination_column, geocoded_path, map_path):
    """Process the file in the background and update job status"""
    try:
        # Process in batches of 30 rows
        create_map(file_path, origin_column, destination_column, geocoded_path, map_path, 
                  max_rows=200, job_id=job_id)
        
        # Update job status when complete
        app.config['JOBS'][job_id]['status'] = 'complete'
        app.config['JOBS'][job_id]['progress'] = 100
    except Exception as e:
        # Update job status on error
        app.config['JOBS'][job_id]['status'] = 'error'
        app.config['JOBS'][job_id]['error'] = str(e)
        print(f"Background processing error: {str(e)}")

@app.route('/job-status/<job_id>')
def job_status(job_id):
    """Check the status of a background geocoding job"""
    if job_id in app.config['JOBS']:
        job = app.config['JOBS'][job_id]
        return jsonify(job)
    else:
        return jsonify({'status': 'not_found'}), 404

@app.route('/result/<job_id>')
def job_result(job_id):
    """Show results after background processing is complete"""
    if job_id in app.config['JOBS'] and app.config['JOBS'][job_id]['status'] == 'complete':
        job = app.config['JOBS'][job_id]
        return render_template('result.html', map_file=f"map_{job['unique_id']}.html")
    elif job_id in app.config['JOBS'] and app.config['JOBS'][job_id]['status'] == 'error':
        return f"Error creating map: {app.config['JOBS'][job_id].get('error', 'Unknown error')}"
    else:
        return redirect(url_for('index'))

@app.route('/maps/<filename>')
def get_map(filename):
    return send_from_directory(app.config['MAP_FOLDER'], filename)

@app.route('/download/map/<filename>')
def download_map(filename):
    response = send_from_directory(app.config['MAP_FOLDER'], filename, as_attachment=True)
    # Set headers to force download
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-Type"] = "text/html"
    return response

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

def create_map(file_path, origin_column, destination_column, geocoded_path, map_path, max_rows=None, job_id=None):
    """Create a map from the CSV file without using pandas"""
    # Read the CSV file
    data = []
    headers = []
    
    with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        headers = next(reader)  # Get the headers
        
        # Find the indices of the origin and destination columns
        try:
            origin_idx = headers.index(origin_column)
            dest_idx = headers.index(destination_column)
        except ValueError:
            raise ValueError(f"Column '{origin_column}' or '{destination_column}' not found in CSV")
        
        # Read all rows, but limit if max_rows is specified
        for i, row in enumerate(reader):
            data.append(row)
            if max_rows is not None and i >= max_rows - 1:
                break
    
    print(f"Successfully loaded CSV with {len(data)} rows")
    
    # Prepare data structure for geocoding
    geocoded_data = []
    headers = headers + ['ID', 'Origin_Latitude', 'Origin_Longitude', 'Destination_Latitude', 'Destination_Longitude']
    
    # Create dictionaries to cache geocoded results to avoid duplicate API calls
    origin_cache = {}
    dest_cache = {}
    
    # Geocode addresses
    print("Starting geocoding process...")
    for i, row in enumerate(data):
        try:
            # Update progress if job_id is provided
            if job_id and i % 5 == 0:  # Update every 5 rows
                progress = min(int((i / len(data)) * 100), 99)  # Keep it under 100 until complete
                app.config['JOBS'][job_id]['progress'] = progress
                print(f"Geocoding progress: {progress}%")
            
            # Create a new row with the original data
            new_row = row.copy()
            
            # Add ID
            new_row.append(str(i + 1))
            
            # Geocode the origin address
            origin_address = str(row[origin_idx]).strip()
            if origin_address in origin_cache:
                # Use cached result
                origin_location = origin_cache[origin_address]
            else:
                # Geocode and cache result
                print(f"Geocoding origin ({i+1}/{len(data)}): {origin_address}")
                origin_location = get_lat_long(origin_address)
                origin_cache[origin_address] = origin_location
            
            # Add origin coordinates
            if origin_location is not None:
                new_row.append(str(origin_location[0]))  # Latitude
                new_row.append(str(origin_location[1]))  # Longitude
            else:
                new_row.append('')
                new_row.append('')
            
            # Geocode the destination address
            dest_address = str(row[dest_idx]).strip()
            if dest_address in dest_cache:
                # Use cached result
                dest_location = dest_cache[dest_address]
            else:
                # Geocode and cache result
                print(f"Geocoding destination ({i+1}/{len(data)}): {dest_address}")
                dest_location = get_lat_long(dest_address)
                dest_cache[dest_address] = dest_location
            
            # Add destination coordinates
            if dest_location is not None:
                new_row.append(str(dest_location[0]))  # Latitude
                new_row.append(str(dest_location[1]))  # Longitude
            else:
                new_row.append('')
                new_row.append('')
            
            geocoded_data.append(new_row)
            
            # Add a small delay to avoid hitting API limits
            time.sleep(0.2)
            
        except Exception as e:
            print(f"Error processing row {i}: {e}")
    
    # Save the geocoded data
    with open(geocoded_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        writer.writerows(geocoded_data)
    
    print(f"Saved geocoded data to {geocoded_path}")
    
    # Filter out rows with missing coordinates
    complete_data = []
    for row in geocoded_data:
        # Check if all coordinate fields have values
        id_idx = headers.index('ID')
        origin_lat_idx = headers.index('Origin_Latitude')
        origin_lon_idx = headers.index('Origin_Longitude')
        dest_lat_idx = headers.index('Destination_Latitude')
        dest_lon_idx = headers.index('Destination_Longitude')
        
        if (row[origin_lat_idx] and row[origin_lon_idx] and 
            row[dest_lat_idx] and row[dest_lon_idx]):
            complete_data.append(row)
    
    print(f"Found {len(complete_data)} rows with complete geocoding")
    
    if len(complete_data) == 0:
        raise ValueError("No complete geocoded entries found. Map cannot be created.")
    
    # Create a map centered around the continental US
    m = folium.Map(location=[39.8283, -98.5795], zoom_start=4)
    
    # Use MarkerClusters to handle many points
    origin_cluster = MarkerCluster(name="Origin Locations", show=True)
    dest_cluster = MarkerCluster(name="Destination Locations", show=True)
    
    # Create a feature group for lines that can be toggled (off by default)
    lines = folium.FeatureGroup(name="Routes", show=False)
    
    # Count frequency of each location
    origin_counts = {}
    dest_counts = {}
    
    for row in complete_data:
        origin_address = row[origin_idx]
        dest_address = row[dest_idx]
        
        if origin_address in origin_counts:
            origin_counts[origin_address] += 1
        else:
            origin_counts[origin_address] = 1
            
        if dest_address in dest_counts:
            dest_counts[dest_address] += 1
        else:
            dest_counts[dest_address] = 1
    
    # Store unique locations to prevent duplicates
    unique_origins = {}
    unique_dests = {}
    
    # Add markers for origin and destination locations
    for row in complete_data:
        id_value = row[headers.index('ID')]
        origin_address = row[origin_idx]
        dest_address = row[dest_idx]
        
        # Create popup content with frequency info
        origin_count = origin_counts.get(origin_address, 0)
        dest_count = dest_counts.get(dest_address, 0)
        
        origin_popup = f"<b>Origin:</b> {origin_address}<br><b>Frequency:</b> {origin_count} shipments"
        dest_popup = f"<b>Destination:</b> {dest_address}<br><b>Frequency:</b> {dest_count} shipments"
        
        # Get coordinates
        origin_lat = float(row[headers.index('Origin_Latitude')])
        origin_lon = float(row[headers.index('Origin_Longitude')])
        dest_lat = float(row[headers.index('Destination_Latitude')])
        dest_lon = float(row[headers.index('Destination_Longitude')])
        
        origin_coords = (origin_lat, origin_lon)
        dest_coords = (dest_lat, dest_lon)
        
        # Origin marker - check for duplicates
        origin_key = f"{origin_lat:.6f},{origin_lon:.6f}"
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
        dest_key = f"{dest_lat:.6f},{dest_lon:.6f}"
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