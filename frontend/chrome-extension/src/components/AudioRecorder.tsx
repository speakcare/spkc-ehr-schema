import React, { useState, useRef } from 'react';
import { Button, Box, Typography, IconButton } from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import StopIcon from '@mui/icons-material/Stop';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';


// interface AudioRecorderProps {
//   onAudioBlobReady: (audioBlob: Blob, fileName: string) => void;
// }

interface AudioRecorderProps {
  audioType: string;
  onAudioBlobReady: (audioBlob: Blob) => void;
}

const AudioRecorder: React.FC<AudioRecorderProps> = ({ audioType, onAudioBlobReady }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
  const [audioChunks, setAudioChunks] = useState<Blob[]>([]);

  const timerRef = useRef<number | null>(null);

  const startRecording = async () => {
    setIsRecording(true);
    setIsPaused(false);
    setAudioChunks([]);
    setRecordingTime(0);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: audioType });
      setMediaRecorder(recorder);
      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          setAudioChunks((prevChunks) => [...prevChunks, event.data]);
          console.log('Audio chunk received:', event.data);
        }
      };
      console.log('Starting recording:', recorder);
      recorder.start(500);
      // Start timer
      timerRef.current = window.setInterval(() => {
        setRecordingTime((prevTime) => prevTime + 1);
      }, 1000);
    } catch (error) {
      console.error("Error starting recording:", error);
      if (error instanceof DOMException) {
        // Now we know `error` is a DOMException, we can access name and message
        console.error("Error name:", error.name);
        console.error("Error message:", error.message);
      }
    }
  };

  const pauseRecording = () => {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      mediaRecorder.pause();
      setIsPaused(true);
      if (timerRef.current) {
        clearInterval(timerRef.current);
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
        clearInterval(timerRef.current);
      }
      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunks, { type: audioType });
        console.log('Audio Blob:', audioBlob);
        if (audioBlob.size > 0) {
          const audioUrl = URL.createObjectURL(audioBlob);
          console.log('Blob URL:', audioUrl);
          setAudioUrl(audioUrl);
          onAudioBlobReady(audioBlob);
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
    <Box sx={{ marginBottom: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        {!isRecording && (
          <Button variant="contained" color="primary" onClick={startRecording} startIcon={<FiberManualRecordIcon />}>
            Start Recording
          </Button>
        )}
        {isRecording && !isPaused && (
          <IconButton color="secondary" onClick={pauseRecording}>
            <PauseIcon />
          </IconButton>
        )}
        {isPaused && (
          <IconButton color="secondary" onClick={resumeRecording}>
            <PlayArrowIcon />
          </IconButton>
        )}
        {isRecording && (
          <IconButton color="error" onClick={stopRecording}>
            <StopIcon />
          </IconButton>
        )}
      </Box>
      <Typography variant="body1" sx={{ marginTop: 1 }}>
        Recording Time: {formatTime(recordingTime)}
      </Typography>

      {audioUrl && (
        <Box sx={{ marginTop: 2 }}>
          <audio controls src={audioUrl}></audio>
        </Box>
      )}
    </Box>
  );
};

export default AudioRecorder;
