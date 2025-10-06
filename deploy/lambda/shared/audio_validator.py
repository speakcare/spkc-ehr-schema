# audio_validator.py
"""
Shared audio validation utilities for Lambda handlers.
Validates audio file format, size, and basic integrity.
"""

import os
import logging
from typing import Tuple, Dict, Any

logger = logging.getLogger(__name__)

# Audio size constants
MIN_AUDIO_SIZE_BYTES = 1024  # Minimum reasonable size for audio
MAX_SIGN_IN_AUDIO_SIZE_BYTES = int(os.getenv('MAX_SIGN_IN_AUDIO_SIZE_BYTES', '1048576'))  # Default 1MB

# Supported audio formats
SUPPORTED_EXTENSIONS = ['.mp3', '.m4a', '.wav', '.webm', '.ogg', '.flac', '.aac']
SUPPORTED_CONTENT_TYPES = [
    'audio/mpeg', 'audio/mp3', 'audio/mp4', 'audio/m4a', 'audio/wav', 
    'audio/webm', 'audio/ogg', 'audio/flac', 'audio/aac', 'audio/x-m4a'
]

# Audio file signatures (magic bytes)
AUDIO_SIGNATURES = [
    b'ID3',  # MP3 with ID3 tag
    b'\xff\xfb',  # MP3 frame header
    b'\xff\xf3',  # MP3 frame header
    b'\xff\xf2',  # MP3 frame header
    b'RIFF',  # WAV/WebM
    b'OggS',  # OGG
    b'fLaC',  # FLAC
    b'\x00\x00\x00\x20ftypM4A',  # M4A
    b'\x00\x00\x00\x18ftypM4A',  # M4A variant
]


def validate_audio_size(audio_data: bytes, max_size: int = None) -> Tuple[bool, str, str]:
    """
    Validate audio file size.
    
    Args:
        audio_data: Raw audio bytes
        max_size: Maximum allowed size (defaults to MAX_SIGN_IN_AUDIO_SIZE_BYTES)
    
    Returns:
        tuple: (is_valid, error_message, error_code)
    """
    if max_size is None:
        max_size = MAX_SIGN_IN_AUDIO_SIZE_BYTES
    
    size = len(audio_data)
    
    if size < MIN_AUDIO_SIZE_BYTES:
        return False, f"Audio file too small or corrupted. Minimum size: {MIN_AUDIO_SIZE_BYTES} bytes", "AUDIO_INVALID"
    
    if size > max_size:
        return False, f"Audio file too large. Maximum size: {max_size} bytes", "AUDIO_INVALID"
    
    return True, "Audio size is valid", ""


def validate_audio_format(recording_data: Dict[str, Any]) -> Tuple[bool, str, str]:
    """
    Validate audio file format based on filename, content-type, and file signature.
    
    Args:
        recording_data: Dictionary containing 'filename', 'content_type', and 'content'
    
    Returns:
        tuple: (is_valid, error_message, error_code)
    """
    try:
        filename = recording_data.get('filename', '').lower()
        content_type = recording_data.get('content_type', '').lower()
        content = recording_data.get('content', b'')
        
        # Check file extension
        has_valid_extension = any(filename.endswith(ext) for ext in SUPPORTED_EXTENSIONS)
        
        # Check content type
        has_valid_content_type = any(content_type.startswith(ct) for ct in SUPPORTED_CONTENT_TYPES)
        
        # Primary validation: must have either valid extension OR valid content-type
        if not has_valid_extension and not has_valid_content_type:
            return False, f"Invalid audio format. Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}. Got filename: '{filename}', content-type: '{content_type}'", "AUDIO_INVALID"
        
        # Secondary validation: check file signature (optional, logs warning only)
        try:
            content_bytes = content[:12]  # Check first 12 bytes
            has_valid_signature = any(content_bytes.startswith(sig) for sig in AUDIO_SIGNATURES)
            
            if not has_valid_signature:
                logger.warning("Audio file may not have valid audio signature. Filename: %s, Content-Type: %s", filename, content_type)
                # Don't fail here as some valid audio files might not match these signatures
                
        except Exception as e:
            logger.warning("Could not validate audio file signature: %s", e)
            # Don't fail here as signature validation is not critical
        
        return True, "Audio format is valid", ""
        
    except Exception as e:
        return False, f"Audio format validation failed: {str(e)}", "AUDIO_INVALID"


def validate_audio_comprehensive(recording_data: Dict[str, Any], max_size: int = None) -> Tuple[bool, str, str]:
    """
    Comprehensive audio validation including size and format checks.
    
    Args:
        recording_data: Dictionary containing 'filename', 'content_type', and 'content'
        max_size: Maximum allowed size (defaults to MAX_SIGN_IN_AUDIO_SIZE_BYTES)
    
    Returns:
        tuple: (is_valid, error_message, error_code)
    """
    try:
        content = recording_data.get('content', b'')
        
        # Validate size first
        size_valid, size_msg, size_code = validate_audio_size(content, max_size)
        if not size_valid:
            return size_valid, size_msg, size_code
        
        # Validate format
        format_valid, format_msg, format_code = validate_audio_format(recording_data)
        if not format_valid:
            return format_valid, format_msg, format_code
        
        return True, "Audio validation passed", ""
        
    except Exception as e:
        return False, f"Audio validation failed: {str(e)}", "AUDIO_INVALID"
