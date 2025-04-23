<!-- templates/index.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mapping Tool</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            padding-top: 20px;
            background-color: #f8f9fa;
        }
        .container {
            max-width: 800px;
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        h1 {
            margin-bottom: 30px;
            color: #0d6efd;
        }
        .upload-area {
            border: 2px dashed #0d6efd;
            border-radius: 5px;
            padding: 25px;
            text-align: center;
            margin-bottom: 20px;
            cursor: pointer;
        }
        .upload-area:hover {
            background-color: #f8f9fa;
        }
        .hidden {
            display: none;
        }
        .info-box {
            background-color: #e7f3ff;
            border-left: 4px solid #0d6efd;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 0 5px 5px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="text-center">Location Mapping Tool</h1>
        
        <div class="info-box">
            <h5>How it works:</h5>
            <ol>
                <li>Upload your CSV file containing origin and destination data</li>
                <li>Select which columns contain your origin and destination addresses/zip codes</li>
                <li>The tool will geocode the locations and create an interactive map</li>
                <li>You can download both the map and the geocoded data</li>
            </ol>
        </div>
        
        <form action="/upload" method="post" enctype="multipart/form-data">
            <div class="upload-area" id="uploadArea">
                <img src="https://cdn-icons-png.flaticon.com/512/4208/4208479.png" width="80" class="mb-3">
                <h4>Drag and drop your CSV file here</h4>
                <p class="text-muted">or click to browse files</p>
                <input type="file" id="fileInput" name="file" class="hidden" accept=".csv">
            </div>
            
            <div class="d-grid gap-2">
                <button type="submit" class="btn btn-primary btn-lg">Upload and Continue</button>
            </div>
        </form>
        
        <div class="mt-4">
            <h5>Requirements:</h5>
            <ul>
                <li>CSV file with data about origins and destinations</li>
                <li>The file should contain columns for origin addresses/zip codes and destination addresses/zip codes</li>
                <li>For best results with zip codes, ensure they're properly formatted</li>
            </ul>
        </div>
    </div>

    <script>
        // Handle drag and drop functionality
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        
        uploadArea.addEventListener('click', () => {
            fileInput.click();
        });
        
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) {
                uploadArea.innerHTML = `<h4>Selected: ${fileInput.files[0].name}</h4>`;
            }
        });
        
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.style.backgroundColor = '#f8f9fa';
        });
        
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.style.backgroundColor = '';
        });
        
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.style.backgroundColor = '';
            
            if (e.dataTransfer.files.length > 0) {
                fileInput.files = e.dataTransfer.files;
                uploadArea.innerHTML = `<h4>Selected: ${e.dataTransfer.files[0].name}</h4>`;
            }
        });
    </script>
</body>
</html>

<!-- templates/select_columns.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Select Columns - Mapping Tool</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            padding-top: 20px;
            background-color: #f8f9fa;
        }
        .container {
            max-width: 800px;
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        h1 {
            margin-bottom: 30px;
            color: #0d6efd;
        }
        .info-box {
            background-color: #e7f3ff;
            border-left: 4px solid #0d6efd;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 0 5px 5px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="text-center">Select Columns</h1>
        
        <div class="info-box">
            <p>Your CSV file has been uploaded. Now, please select which columns contain your origin and destination addresses or zip codes.</p>
        </div>
        
        <form action="/process" method="post">
            <input type="hidden" name="file_path" value="{{ file_path }}">
            
            <div class="mb-3">
                <label for="originColumn" class="form-label">Origin Column:</label>
                <select name="origin_column" id="originColumn" class="form-select" required>
                    <option value="" disabled selected>Select the column with origin addresses/zip codes</option>
                    {% for column in columns %}
                    <option value="{{ column }}">{{ column }}</option>
                    {% endfor %}
                </select>
                <div class="form-text">This column should contain the starting locations (addresses or zip codes)</div>
            </div>
            
            <div class="mb-3">
                <label for="destinationColumn" class="form-label">Destination Column:</label>
                <select name="destination_column" id="destinationColumn" class="form-select" required>
                    <option value="" disabled selected>Select the column with destination addresses/zip codes</option>
                    {% for column in columns %}
                    <option value="{{ column }}">{{ column }}</option>
                    {% endfor %}
                </select>
                <div class="form-text">This column should contain the ending locations (addresses or zip codes)</div>
            </div>
            
            <div class="d-grid gap-2">
                <button type="submit" class="btn btn-primary btn-lg">Create Map</button>
            </div>
            
            <div class="alert alert-warning mt-3" role="alert">
                <strong>Note:</strong> Depending on the size of your dataset, the geocoding process may take some time. Please be patient.
            </div>
        </form>
    </div>
</body>
</html>

<!-- templates/result.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Map Results - Mapping Tool</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            padding-top: 20px;
            background-color: #f8f9fa;
        }
        .container {
            max-width: 800px;
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        h1 {
            margin-bottom: 30px;
            color: #0d6efd;
        }
        .map-container {
            margin: 20px 0;
            border: 1px solid #dee2e6;
            border-radius: 5px;
            overflow: hidden;
        }
        iframe {
            width: 100%;
            height: 500px;
            border: none;
        }
        .btn-container {
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="text-center">Your Map is Ready!</h1>
        
        <div class="alert alert-success" role="alert">
            <strong>Success!</strong> Your locations have been geocoded and mapped.
        </div>
        
        <div class="map-container">
            <iframe src="/maps/{{ map_file }}" title="Interactive Map"></iframe>
        </div>
        
        <div class="btn-container">
            <a href="/maps/{{ map_file }}" class="btn btn-primary" target="_blank">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-map me-2" viewBox="0 0 16 16">
                    <path fill-rule="evenodd" d="M15.817.113A.5.5 0 0 1 16 .5v14a.5.5 0 0 1-.402.49l-5 1a.5.5 0 0 1-.196 0L5.5 15.01l-4.902.98A.5.5 0 0 1 0 15.5v-14a.5.5 0 0 1 .402-.49l5-1a.5.5 0 0 1 .196 0L10.5.99l4.902-.98a.5.5 0 0 1 .415.103zM10 1.91l-4-.8v12.98l4 .8V1.91zm1 12.98 4-.8V1.11l-4 .8v12.98zm-6-.8V1.11l-4 .8v12.98l4-.8z"/>
                </svg>
                Open Map in New Tab
            </a>
            
            <a href="/geocoded/geocoded_{{ map_file|replace('map_', '')|replace('.html', '.csv') }}" class="btn btn-outline-primary" download>
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-download me-2" viewBox="0 0 16 16">
                    <path d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5z"/>
                    <path d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708l3 3z"/>
                </svg>
                Download Geocoded Data
            </a>
        </div>
        
        <div class="mt-4">
            <a href="/" class="btn btn-outline-secondary">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-arrow-left me-2" viewBox="0 0 16 16">
                    <path fill-rule="evenodd" d="M15 8a.5.5 0 0 0-.5-.5H2.707l3.147-3.146a.5.5 0 1 0-.708-.708l-4 4a.5.5 0 0 0 0 .708l4 4a.5.5 0 0 0 .708-.708L2.707 8.5H14.5A.5.5 0 0 0 15 8z"/>
                </svg>
                Create Another Map
            </a>
        </div>
        
        <div class="alert alert-info mt-4" role="alert">
            <h5>Map Tips:</h5>
            <ul class="mb-0">
                <li>Click on markers to see detailed information</li>
                <li>Use the layer control in the top right to toggle different map elements</li>
                <li>For better performance, turn off the "Routes" layer if there are many points</li>
                <li>Click on clusters to zoom in and see individual points</li>
            </ul>
        </div>
    </div>
</body>
</html>