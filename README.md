# SpeakCare Demo

This project is a demo for the SpeakCare product, demonstrating nursing charting using speech-to-text technology. For the purpose of this demo, we are using a mockup EHR built on Airtable.

## 🚀 Installation

### Prerequisites

1. **Install Python 3.13**:
   ```bash
   # On macOS with Homebrew
   brew install python@3.13
   
   # Or download from https://www.python.org/downloads/
   # Verify installation
   python3.13 --version

   # Add Python 3.13 as 'python3'
   export PATH="/Library/Frameworks/Python.framework/Versions/3.13/bin:$PATH"
   ```

2. **Install Poetry**:
   ```bash
   # Install Poetry using the official installer
   curl -sSL https://install.python-poetry.org | python3.13 -
   
   # Or install via pip (if you prefer)
   python3.13 -m pip install poetry
   
   # Add Poetry to your PATH
   export PATH="$HOME/.local/bin:$PATH"

   # Verify installation
   poetry --version
   ```

### ⚡ Quick PATH Setup (Most Common Issue)
If you get "command not found" errors, add these to your shell configuration:

```bash
# Add to ~/.zshrc or ~/.bashrc
export PATH="/Library/Frameworks/Python.framework/Versions/3.13/bin:$PATH"
export PATH="$HOME/.local/bin:$PATH"
```

### Project Setup

```bash
# Install all dependencies (creates virtual environment automatically)
poetry install

# Verify everything is working
poetry run python --version
```

## 📋 Quick Commands

### Basic Poetry Commands
```bash
# Add a new dependency
poetry add package-name

# Update dependencies
poetry update

# Show installed packages
poetry show

# Remove a dependency
poetry remove package-name
```

### Running Your Application
```bash
# Run the main application
poetry run python backend/speakcare_process.py -r <audio_file> -c <table1> <table2>

# Run specific tests
poetry run python -m unittest backend/speakcare_emr_utils_test.py

# Run all tests in backend directory
poetry run python -m unittest discover backend/ -p "*_test.py"

# Run tests with pytest (if you prefer pytest)
poetry run pytest backend/speakcare_emr_utils_test.py -v
poetry run pytest backend/ -v --ignore=backend/tools/
```

### Alternative: Using Poetry Environment Activation
```bash
# Activate the Poetry environment (Poetry 2.0+)
poetry env activate

# Then run commands directly (no need for 'poetry run')
python backend/speakcare_process.py -r <audio_file> -c <table1> <table2>
python -m unittest backend/speakcare_emr_utils_test.py
pytest backend/name_matching_test.py -v

# Deactivate when done
deactivate
```

## Running the Project

### 1. Running from Command Line
You can run the project from the command line using the speakcare.py script. This script accepts several command line arguments:
```sh
poetry run python backend/speakcare_process.py [arguments]
```

Command Line Arguments:
*  -h, --help            show this help message and exit
*  -l, --list-devices    Print input devices list and exit
*  -s SECONDS, --seconds SECONDS
                         Recording duration (default: 30)
*  -o OUTPUT_PREFIX, --output-prefix OUTPUT_PREFIX
                         Output file prefix (default: output)
*  -t TABLE, --table TABLE
                         Table name (suported tables: ['Blood Pressures', 'Weights', 'Admission', 'Temperatures', 'Pulses']
*  -d, --dryrun          If dryrun write JSON only and do not create EMR record
*  -a AUDIO_DEVICE, --audio-device AUDIO_DEVICE
                         Audio device index (required)

Example usage:
```sh
poetry run python backend/speakcare_process.py -t 'Temperatures' -o 'temperature' -a 0
```

### 2. Running the Flask Server
You can also run the Flask server to provide a web interface for the demo:
```sh
./run_server.sh
```
This will start the Flask server, and you can access the web interface by navigating to http://localhost:3000 in your web browser.

## Environment Variables
Ensure you have the following environment variables set in your .env file, as shown in the .env_example file:
* AIRTABLE_API_KEY='airtable_api_key'
* AIRTABLE_APP_BASE_ID = 'airtable_app_base_id'
* OPENAI_API_KEY='openai_api_key'
* LOGGER_LEVEL='DEBUG'
* UT_RUN_SKIPPED_TESTS=False
* DB_DIRECTORY='db'

## Viewing the docs
* Go to <speackare-hostname>/redoc to see the API documenation in redoc.
* Go to <speackare-hostname>/docs to see the Swagger documentation of the api. You can also try out the API through the Swagger doc page.
* Note: when running locally the speakcare-hostname is http://localhost:5000. You can change the port name by changing the environment variable APP_PORT in your .env file.

## Viewing the sqlite database content
From the backend directory run the datasette server.
```sh
datasette serve db/medical_records.db db/transcripts.db 
```
You can access the datasette server on port 8001:  http://localhost:8001

## 🔧 Configuration Files

- **`pyproject.toml`** - Main Poetry configuration with dependencies and project metadata
- **`poetry.lock`** - Lock file with exact dependency versions (auto-generated), shouldn't be uploaded to GIT

## Summary

This README file provides a comprehensive guide on installing and running the SpeakCare demo project using Poetry for dependency management. It includes instructions for setting up Python 3.13, installing Poetry, running the project from the command line, and starting the Flask server. Additionally, it explains the required environment variables and provides examples of how to use the command line arguments.