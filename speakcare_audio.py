import pyaudio
import wave
import audioop
import time
import argparse
from speakcare_logging import create_logger
from os_utils import ensure_directory_exists

logger = create_logger(__name__)

# List all available audio devices
def print_devices():
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

def record_audio(device_index: int, duration: int =5, output_filename="output.wav"):
    samples_per_chunk = 1024  # Record in chunks of 1024 samples
    sample_format = pyaudio.paInt16  # 16 bits per sample
    channels = 1
    fs = 44100  # Record at 44100 samples per second

    # p = pyaudio.PyAudio()  # Create an interface to PortAudio
    # for i in range(p.get_device_count()):
    #     info = p.get_device_info_by_index(i)
    #     print(f"Device {i}: {info['name']}")

    print(f'Recording device index: {device_index} for {duration} seconds into {output_filename}')

  
    try:  
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16,
                        channels=channels,
                        rate=fs,
                        input=True,
                        input_device_index=device_index,
                        frames_per_buffer=samples_per_chunk)

        print("Recording from:", p.get_device_info_by_index(device_index)['name'])


        frames = []  # Initialize array to store frames

        # Store data in chunks for the duration specified
        num_chunks = int(fs / samples_per_chunk * duration)
        for i in range(0, int(num_chunks)):
            data = stream.read(samples_per_chunk)
            frames.append(data)

    except Exception as e:
        logger.error(f"Error occurred while recording audio: {e}")
        return
    
    finally:
        # Stop and close the stream
        stream.stop_stream()
        stream.close()
        # Terminate the PortAudio interface
        p.terminate()

    logger.info('Finished recording.')

    # Save the recorded data as a WAV file
    with wave.open(output_filename, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(p.get_sample_size(sample_format))
        wf.setframerate(fs)
        wf.writeframes(b''.join(frames))

    logger.info(f"Audio saved to {output_filename}")



def record_audio(device_index: int, duration: int = 5, output_filename="output.wav", silence_threshold=500, silence_duration=2, max_silence=5):
    samples_per_chunk = 1024  # Record in chunks of 1024 samples
    sample_format = pyaudio.paInt16  # 16 bits per sample
    channels = 1
    fs = 44100  # Record at 44100 samples per second

    print(f'Recording device index: {device_index} for {duration} seconds into {output_filename}')

    try:  
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16,
                        channels=channels,
                        rate=fs,
                        input=True,
                        input_device_index=device_index,
                        frames_per_buffer=samples_per_chunk)

        print("Recording from:", p.get_device_info_by_index(device_index)['name'])

        silence_start = None

        with wave.open(output_filename, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(p.get_sample_size(sample_format))
            wf.setframerate(fs)

            while True:
                data = stream.read(samples_per_chunk)
                rms = audioop.rms(data, 2)  # Calculate the RMS of the chunk (2 bytes per sample)

                if rms >= silence_threshold or\
                      (silence_start and (time.time() - silence_start) < silence_duration):
                    if silence_start and rms >= silence_threshold:
                        silence_start = None
                        print("Sound detected, resuming recording...")

                    wf.writeframes(data)  # Write the audio data directly to the file

                else:
                    if silence_start is None:
                        silence_start = time.time()

                    # If silence exceeds max_silence, stop recording
                    if time.time() - silence_start > max_silence:
                        print(f"Silence detected for more than {max_silence} seconds, stopping recording.")
                        break

                    time.sleep(0.1)  # Sleep for 0.1 seconds to reduce CPU usage


                # Check if the recording duration has been reached
                if wf.tell() >= fs * duration * channels * p.get_sample_size(sample_format):
                    break

    except Exception as e:
        logger.error(f"Error occurred while recording audio: {e}")
        return
    
    finally:
        # Stop and close the stream
        stream.stop_stream()
        stream.close()
        # Terminate the PortAudio interface
        p.terminate()

    logger.info('Finished recording.')

    logger.info(f"Audio saved to {output_filename}")




def main():
    # Parse command line arguments
    output_dir = "recordings"
    parser = argparse.ArgumentParser(description='Audio input recorder.')
    parser.add_argument('-l', '--list', action='store_true', help='Print devices list and exit')
    parser.add_argument('-s', '--seconds', type=int, default=30, help='Recording duration (default: 5)')
    parser.add_argument('-o', '--output', type=str, default="output.wav", help='Output filename (default: output.wav)')
    parser.add_argument('-d', '--device', type=int, default=0, help='Device index (default: 0)')
    
    args = parser.parse_args()
    
    if args.list:
        print_devices()
        exit(0)
    
    if (device_index := args.device) is None:
        print (f"Recording audio from device index: {device_index}")
        print("Please provide a valid device index (-d | --devidce) to record audio.")
        print_devices()
        exit(1)
    
    
    duration = args.seconds
    output_filename = f'{output_dir}/{args.output}'
    ensure_directory_exists(output_filename) 
    record_audio(device_index=device_index,  duration=duration, output_filename=output_filename)

if __name__ == '__main__':
    main()

    silence_start = None

