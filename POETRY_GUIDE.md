# Poetry Usage Guide for SpeakCare Demo

## 🚀 Installation

### ⚡ Quick PATH Setup (Most Common Issue)
If you get "command not found" errors, add these to your shell configuration:

### Prerequisites
1. **Install Python 3.13**:
   ```bash
   # On macOS with Homebrew
   brew install python@3.13
   
   # Or download from https://www.python.org/downloads/
   # Verify installation
   python3.13 --version

   # Add Python 3.13 as 'python3'
   export PATH="/Library/Frameworks/Python.framework/Versions/3.13/bin:$PATH
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


### Initial Setup
```bash

# Install all dependencies (creates virtual environment automatically) - should be run inside the project folder
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
poetry run python -m unittest backend/name_matching_test.py

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
python -m unittest backend/name_matching_test.py
pytest backend/name_matching_test.py -v

# Deactivate when done
deactivate
```


## 🔧 Configuration Files

- **`pyproject.toml`** - Main Poetry configuration with dependencies and project metadata
- **`poetry.lock`** - Lock file with exact dependency versions (auto-generated)