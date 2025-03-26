import React from 'react';
import { Button, Box } from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import UploadIcon from '@mui/icons-material/Upload';

interface AudioButtonsProps {
  audioBlob: Blob | null;
  audioType: string;
  onSave: () => void;
  onLoad: (event: React.ChangeEvent<HTMLInputElement>) => void;
}

const AudioButtons: React.FC<AudioButtonsProps> = ({ 
  audioBlob, 
  audioType, 
  onSave, 
  onLoad 
}) => {
  return (
    <Box sx={{ display: 'flex', gap: 2, marginTop: 2 }}>
      <Button
        variant="outlined"
        color="primary"
        fullWidth
        onClick={onSave}
        disabled={!audioBlob}
        startIcon={<SaveIcon />}
      >
        Save Audio
      </Button>
      <Button
        variant="outlined"
        color="primary"
        fullWidth
        component="label"
        startIcon={<UploadIcon />}
      >
        Load Audio
        <input
          type="file"
          hidden
          accept={audioType}
          onChange={onLoad}
        />
      </Button>
    </Box>
  );
};

export default AudioButtons; 