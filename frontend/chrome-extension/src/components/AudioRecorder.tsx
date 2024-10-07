import React, { useState, useRef } from 'react';

interface AudioRecorderProps {
  onAudioBlobReady: (audioBlob: Blob, fileName: string) => void;
}

const AudioRecorder: React.FC<AudioRecorderProps>  = ({ onAudioBlobReady }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0); // Timer state
  const [audioUrl, setAudioUrl] = useState<string | null>(null); // URL for recorded audio
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
  const [audioChunks, setAudioChunks] = useState<Blob[]>([]); // Array to hold audio data chunks

  const timerRef = useRef<number | null>(null); // Timer reference

  // Function to handle starting the recording
  const startRecording = async () => {
    setIsRecording(true);
    setIsPaused(false);
    setAudioChunks([]);
    setRecordingTime(0);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      setMediaRecorder(recorder);
      recorder.ondataavailable = (event) => {
          if (event.data && event.data.size > 0) {
              setAudioChunks((prevChunks) => [...prevChunks, event.data]);
              console.log('Audio chunk received:', event.data);
        }
      };
      console.log('Starting recording:', recorder);
      recorder.start(1000);

      // Start timer
      timerRef.current = window.setInterval(() => {
        setRecordingTime((prevTime) => prevTime + 1);
      }, 1000);
    } catch (error) {
      if (error instanceof DOMException) {
        // Now we know `error` is a DOMException, we can access name and message
        console.error("Error starting recording:", error);
        console.error("Error name:", error.name);
        console.error("Error message:", error.message);
      } else {
        // Fallback for other types of errors
        console.error("Unknown error:", error);
      }
    }
  };

  // Pause the recording
  const pauseRecording = () => {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      mediaRecorder.pause();
      setIsPaused(true);
      if (timerRef.current) {
        clearInterval(timerRef.current); // Stop timer when paused
      }
    }
  };

  // Resume recording after pausing
  const resumeRecording = () => {
    if (mediaRecorder && mediaRecorder.state === 'paused') {
      mediaRecorder.resume();
      setIsPaused(false);

      timerRef.current = window.setInterval(() => {
        setRecordingTime((prevTime) => prevTime + 1);
      }, 1000);
    }
  };

  // Stop recording
  const stopRecording = () => {
    if (mediaRecorder) {
        mediaRecorder.requestData();  
        setIsRecording(false);
        setIsPaused(false);
        if (timerRef.current) {
            clearInterval(timerRef.current); // Stop timer when recording stops
        }

        mediaRecorder.onstop = () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm; codecs=opus' });
            console.log('Audio Blob:', audioBlob);
            if (audioBlob.size > 0) {
                const audioUrl = URL.createObjectURL(audioBlob);
                console.log('Blob URL:', audioUrl);
                setAudioUrl(audioUrl); // Set the audio URL for playback
                onAudioBlobReady(audioBlob, 'recording.webm');
            } else {
                console.error('Audio Blob is empty or corrupted');
            }
        };
        
        mediaRecorder.stop();
        console.log('Recording stopped');
    }
  };

  
  // Format the timer for display
  const formatTime = (seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds < 10 ? `0${remainingSeconds}` : remainingSeconds}`;
  };

  return (
    <div>
      <div>
        <button onClick={startRecording} disabled={isRecording}>
          Start Recording {isRecording && !isPaused && <span>🔴</span>}
        </button>

        {isRecording && !isPaused && (
          <button onClick={pauseRecording}>
            Pause Recording
          </button>
        )}

        {isPaused && (
          <button onClick={resumeRecording}>
            Resume Recording
          </button>
        )}

        {isRecording && (
          <button onClick={stopRecording}>
            Stop Recording
          </button>
        )}

        <div>Recording Time: {formatTime(recordingTime)}</div>
      </div>

      {audioUrl && (
        <div>
          <audio controls src={audioUrl}></audio>
        </div>
      )}
    </div>
  );
};

export default AudioRecorder;
