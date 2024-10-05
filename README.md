# SpeakCare Demo

This project is a demo for the SpeakCare product, demonstrating nursing charting using speech-to-text technology. For the purpose of this demo, we are using a mockup EHR built on Airtable.

## Installation

### 1. Create a Python Virtual Environment

First, create a virtual environment to isolate the project's dependencies:

```sh
python3 -m venv venv
```
Activate the virtual environment:

* On macOS and Linux:
```sh
source venv/bin/activate
```
On Windows:
```sh
.\venv\Scripts\activate
```
### 2. Install Requirements
Install the required Python packages:
```sh
pip install -r requirements.txt
```
### 3. Install External Dependencies
Ensure you have the external dependencies listed in dependencies.txt installed on your operating system. This file contains a list of system packages that need to be installed for the project to run correctly.

## Running the Project

### 1. Running from Command Line
You can run the project from the command line using the speakcare.py script. This script accepts several command line arguments:
```sh
python3 speakcare.py [arguments]
```
Command Line Arguments
options:
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
python3 speakcare.py -t 'Temperatures' -o 'temperature' -a 0
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

## Viweing the sqlite database content
From the backend direcrtory run the datasette server.
```sh
datasette serve db/medical_records.db db/transcripts.db 
```
You can access the datasette server on port 8001:  http://localhost:8001


## Summary

This README file provides a comprehensive guide on installing and running the SpeakCare demo project. It includes instructions for setting up a Python virtual environment, installing dependencies, running the project from the command line, and starting the Flask server. Additionally, it explains the required environment variables and provides an example of how to use the command line arguments.
