#!/usr/bin/env python3


import pyaudio
import wave
import audioop
import time
from datetime import datetime, timezone
import argparse
import time
import traceback
from speakcare_logging import create_logger
from os_utils import ensure_directory_exists

logger = create_logger(__name__)

# List all available audio devices
def print_audio_devices():
    p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        device_info = f"Device {i}: {info['name']}\n" +\
                      f"  Max Input Channels: {info['maxInputChannels']}\n" +\
                      f"  Max Output Channels: {info['maxOutputChannels']}\n" +\
                      f"  Default Sample Rate: {info['defaultSampleRate']}\n" +\
                      f"  Host API: {info['hostApi']}"
        print(device_info)    
    p.terminate()

def get_input_audio_devices():
    p = pyaudio.PyAudio()
    input_devices = []
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        inputChannels = int(info['maxInputChannels'])
        if inputChannels > 0:
            input_devices.append({'name': info['name'], 'index': i})
    p.terminate()
    return input_devices

def print_input_devices():
    input_devices = get_input_audio_devices()
    logger.debug(f"Input devices:{input_devices}")
    for device in input_devices:
        name = device['name']
        index = device['index']
        print(f"Device {index}: '{name}'")

def check_input_device(device_index: int):
    p = pyaudio.PyAudio()
    try:
        info = p.get_device_info_by_index(device_index)
        inputChannels = int(info['maxInputChannels'])
        return inputChannels > 0
    except OSError as e:
        logger.error(f"Error checking input device {device_index}: {e}")
        return False
    finally:
        p.terminate()



def record_audio(device_index: int, duration: int = 10, output_filename="output.wav", silence_threshold=300, silence_duration=2, max_silence=4):
    samples_per_chunk = 4096  # Record in chunks of 4096 samples
    sample_format = pyaudio.paInt16  # 16 bits per sample
    bytes_per_sample = 2 # 16 bits = 2 bytes
    channels = 1
    fs = 22050  # Record at 22050 samples per second

    error = ""
    stream = None
    audio = None
    try:  
        audio = pyaudio.PyAudio()
        if not audio:
            error = "Failed to initialize PyAudio"
            raise Exception(error)
        
        # if not audio.is_format_supported(sample_format, input_device=device_index):
        #     error = f"Sample format {sample_format} not supported by input device {device_index}"
        #     raise Exception(error)
        frames = [] 
        logger.info(f'Recording device index: {device_index} for {duration} seconds into {output_filename}')
        logger.info(f"Calling audio.open(format={pyaudio.paInt16}, channels={channels}, rate={fs}, input=True, input_device_index={device_index}, frames_per_buffer={samples_per_chunk})")
        stream = audio.open(format=pyaudio.paInt16,
                        channels=channels,
                        rate=fs,
                        input=True,
                        input_device_index=device_index,
                        frames_per_buffer=samples_per_chunk)
        
        if not stream:
            error = "Failed to open audio stream"
            raise Exception(error)
        
        logger.info(f"Recording from: {audio.get_device_info_by_index(device_index)['name']}")

        silence_start = None
        recording_length = 0

        with wave.open(output_filename, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(audio.get_sample_size(sample_format))
            wf.setframerate(fs)

            logger.debug(f"Calling stream.read({samples_per_chunk})")
            while True:
                
                data = stream.read(samples_per_chunk)
                rms = audioop.rms(data, bytes_per_sample)  # Calculate the RMS of the chunk (2 bytes per sample)

                if rms >= silence_threshold or\
                      (silence_start and (time.time() - silence_start) < silence_duration):
                    if silence_start and rms >= silence_threshold:
                        silence_start = None
                        logger.debug("Sound detected, resuming recording...")

                    frames.append(data)
                    if len(frames) >= 10000:
                        wf.writeframes(b''.join(frames))
                        logger.debug(f"Writing {len(frames)} frames to {output_filename}")
                        frames = []

                else:
                    if silence_start is None:
                        silence_start = time.time()

                    # If silence exceeds max_silence, stop recording
                    if time.time() - silence_start > max_silence:
                        logger.info(f"Silence detected for more than {max_silence} seconds, stopping recording.")
                        break

                    #time.sleep(0.01)  # Sleep for 0.1 seconds to reduce CPU usage

                
                # Check if the recording duration has been reached
                if wf.tell() >= fs * duration * channels * audio.get_sample_size(sample_format):
                    break
            if len(frames) > 0:
                wf.writeframes(b''.join(frames))
                logger.debug(f"Writing {len(frames)} frames to {output_filename}")
                frames = []
        recording_length = wf.tell() / (fs * channels * audio.get_sample_size(sample_format))

    except Exception as e:
        logger.error(f"Error occurred while recording audio: {e}")
        traceback.print_exc()
        return 0
    
    finally:
        # Stop and close the stream
        if stream:
            stream.stop_stream()
            stream.close()
        if audio:
            # Terminate the PortAudio interface
            audio.terminate()

    logger.info('Finished recording.')
    logger.info(f"Audio saved to {output_filename}")
    return recording_length




def main():
    # Parse command line arguments
    output_dir = "out/recordings"

    list_parser = argparse.ArgumentParser(description='Speakcare speech to EMR.', add_help=False)
    list_parser.add_argument('-l', '--list', action='store_true', help='Print devices list and exit')
    list_parser.add_argument('-i', '--input-devices', action='store_true', help='Print only the input devices and exit')
    args, remaining_args = list_parser.parse_known_args()
    if args.list:
        print_audio_devices()
        exit(0)

    if args.list:
        print_audio_devices()
        exit(0)

    elif args.input_devices:
        print_input_devices()
        exit(0)

    full_parser = argparse.ArgumentParser(description='Speakcare speech to EMR.', parents=[list_parser])
    full_parser.add_argument('-s', '--seconds', type=int, default=30, help='Recording duration (default: 30)')
    full_parser.add_argument('-o', '--output', type=str, default="output", help='Output file prefix (default: output)')
    full_parser.add_argument('-a', '--audio-device', type=int, required=True, help='Audio device index (required)')
    
    args = full_parser.parse_args()
    
    audio_device = args.audio_device
    if not check_input_device(audio_device):
        print("Please provide a valid device index (-a | --audio-device) to record audio.")
        print_audio_devices()
        exit(1)
    
    # Get the current UTC time
    utc_now = datetime.now(timezone.utc)

    # Format the datetime as a string without microseconds and timezone
    utc_string = utc_now.strftime('%Y-%m-%dT%H:%M:%S')

    duration = args.seconds
    output_filename = f'{output_dir}/{args.output}.{utc_string}.wav'

    ensure_directory_exists(output_filename) 
    logger.info(f"Recording audio from device index {audio_device} for {duration} seconds into {output_filename}")
    record_audio(device_index=audio_device,  duration=duration, output_filename=output_filename)

if __name__ == '__main__':
    main()


