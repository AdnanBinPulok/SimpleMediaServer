# MediaServer Public

A FastAPI-based media server for uploading, serving, compressing, and managing files with rate limiting, authentication, and modular architecture.

> **Note:** This project is about 1.5 years old. While it may not be the most modern or polished, it gets the job done reliably.

## Features

- **File Upload & Download**: Securely upload and serve files with unique filenames and expiration support.
- **Image Compression**: Compress images on upload, auto-rotate based on EXIF, and convert formats.
- **Rate Limiting**: Prevent abuse with per-IP rate limiting on API endpoints.
- **Admin Authorization**: Protect sensitive routes with a master key.
- **Database**: Async SQLite database for file metadata and management.
- **Logging**: Colorful, timestamped logs with file output and WebSocket support.
- **Modular Routing**: Auto-loads routes and pages from folders for easy extensibility.
- **Configurable**: Uses environment variables for all key settings.

## Project Structure

```
main.py                # FastAPI app entrypoint, mounts static, loads routers/pages
modules/
  functions.py         # Utility functions (date parsing, admin auth)
  rate_limiter.py      # RateLimiter class for per-IP request limiting
  storage.py           # Async file upload/delete to remote storage
pages/
  home.py, upload.py   # Page routers for HTML endpoints
routes/
  upload.py            # API for file upload (with admin, rate limit)
  file.py              # API for serving files (view/download)
  delete.py            # API for deleting files (admin only)
  compression.py       # API for image compression
services/
  database.py          # Async SQLite DB connection pool, file metadata
  logging.py           # Logger class with color, file, and WebSocket support
settings/
  config.py            # Loads environment variables, API/storage config
static/                # HTML templates, static assets, error pages
storage/               # Uploaded files (local storage)
```

## Key Modules

### main.py

- Initializes FastAPI app, mounts static files, loads routers from `routes/` and `pages/`.
- Custom error handlers for 404, 429, etc.

### modules/functions.py

- `fetch_date(date_str)`: Parses date strings to UTC datetime.
- `authorize_admin(request)`: Checks for valid admin token in headers.

### modules/rate_limiter.py

- `RateLimiter(times, seconds)`: Per-IP request limiting as FastAPI dependency.

### modules/storage.py

- `upload_file(bytes, filename, expires_at)`: Async upload to remote storage server.
- `delete_image(image_url)`: Async delete from remote storage.

### services/database.py

- `DatabaseConnectionPool`: Async connection pool for SQLite.
- `files_db`: Handles file metadata CRUD.

### services/logging.py

- `Logger`: Colorful, timestamped logs to file/console, supports WebSocket.

### settings/config.py

- Loads environment variables from `.env` in `secrets/`.
- `ApiConfig`, `StorageConfig`: Centralized config for API and storage.

## API Endpoints (examples)

- `POST /api/upload` — Upload a file (admin, rate-limited)
- `GET /file/{file_path}` — Serve/download a file
- `DELETE /api/delete/{file_path}` — Delete a file (admin)
- `POST /api/compress` — Compress an image

## API Usage Examples

### 1. Upload a File

#### Python

```python
import requests

url = "http://localhost:8000/api/upload"
headers = {"Authorization": "Bearer <API_MASTER_KEY>"}
files = {"file": ("example.txt", open("example.txt", "rb"))}

response = requests.post(url, headers=headers, files=files)
print(response.json())
```

#### JavaScript (Node.js)

```js
const axios = require("axios");
const fs = require("fs");
const FormData = require("form-data");

const form = new FormData();
form.append("file", fs.createReadStream("example.txt"));

axios
  .post("http://localhost:8000/api/upload", form, {
    headers: {
      ...form.getHeaders(),
      Authorization: "Bearer <API_MASTER_KEY>",
    },
  })
  .then((res) => console.log(res.data))
  .catch((err) => console.error(err.response?.data || err));
```

---

### 2. Delete a File

> Replace `<file_path>` with the actual file path or ID returned from the upload response.

#### Python

```python
import requests

url = "http://localhost:8000/api/delete/<file_path>"
headers = {"Authorization": "Bearer <API_MASTER_KEY>"}

response = requests.delete(url, headers=headers)
print(response.json())
```

#### JavaScript (Node.js)

```js
const axios = require("axios");

axios
  .delete("http://localhost:8000/api/delete/<file_path>", {
    headers: { Authorization: "Bearer <API_MASTER_KEY>" },
  })
  .then((res) => console.log(res.data))
  .catch((err) => console.error(err.response?.data || err));
```

---

### 3. Compress an Image

To compress an image, send a POST request to:

```
POST /api/compress/{file_path}
```

with a JSON body containing any of the following parameters:

- `quality` (int, default 75): Compression quality (1-100)
- `max_width` (int, optional): Resize image to this width (maintains aspect ratio)
- `to_webp` (bool, default False): Convert to WebP format
- `lossless` (bool, default False): Use lossless compression (WebP only)

#### Python

```python
import requests

url = "http://localhost:8000/api/compress/<file_path>"
headers = {"Authorization": "Bearer <API_MASTER_KEY>", "Content-Type": "application/json"}
data = {
    "quality": 80,
    "max_width": 1024,
    "to_webp": True,
    "lossless": False
}

response = requests.post(url, headers=headers, json=data)
print(response.json())
```

#### JavaScript (Node.js)

```js
const axios = require("axios");

const url = "http://localhost:8000/api/compress/<file_path>";
const data = {
  quality: 80,
  max_width: 1024,
  to_webp: true,
  lossless: false,
};

axios
  .post(url, data, {
    headers: {
      Authorization: "Bearer <API_MASTER_KEY>",
      "Content-Type": "application/json",
    },
  })
  .then((res) => console.log(res.data))
  .catch((err) => console.error(err.response?.data || err));
```

## Installation

1. **Clone the repository:**

```sh
git clone https://github.com/AdnanBinPulok/SimpleMediaServer
cd MediaServer\ Public
```

2. **Install dependencies:**

```sh
pip install -r requirements.txt
```

3. **Set up environment variables:**

- Copy or create a `.env` file in the `secrets/` directory. See `settings/config.py` for required variables.

4. **Run the server:**

```sh
uvicorn main:app --reload
```

## Environment Variables

- `API_NAME`, `API_DESCRIPTION`, `API_HOST`, `API_PORT`, `API_VERSION`, `API_MASTER_KEY`, `API_BASE_URL`
- `STORAGE_*` for remote storage config

## License

MIT
