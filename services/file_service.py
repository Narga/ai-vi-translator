# services/file_service.py - v3.0.0
# Adapted from src/file_writer.py
# File I/O service for plugin architecture

import logging
import shutil
from pathlib import Path
from typing import Optional, List


class FileService:
    """
    Service for file operations: write chunks, combine files, archive.
    
    Registered in ServiceBus for use by workflow and plugins.
    """
    
    def __init__(self, base_dir: Path = None):
        """
        Initialize file service.
        
        Args:
            base_dir: Base directory for file operations (default: current dir)
        """
        self.base_dir = base_dir or Path.cwd()
        self.logger = logging.getLogger(__name__)
        self.logger.info("📁 FileService initialized")
    
    def save_chunk(
        self,
        content: str,
        output_dir: Path,
        filename: str,
        encoding: str = 'utf-8'
    ) -> Path:
        """
        Save translated chunk to file.
        
        Args:
            content: Translated text content
            output_dir: Output directory
            filename: Chunk filename
            encoding: File encoding
        
        Returns:
            Path to saved file
        """
        output_path = Path(output_dir)
        parts_dir = output_path / 'parts'
        parts_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = parts_dir / filename
        
        try:
            with open(file_path, 'w', encoding=encoding) as f:
                f.write(content)
            
            self.logger.info(f"✅ Saved chunk: {filename}")
            return file_path
        
        except Exception as e:
            self.logger.error(f"Failed to save {filename}: {e}")
            raise
    
    def combine_chunks(
        self,
        parts_dir: Path,
        output_file: Path,
        pattern: str = "*.txt",
        separator: str = "\n\n"
    ) -> bool:
        """
        Combine multiple chunk files into single output file.
        
        Args:
            parts_dir: Directory containing chunk files
            output_file: Output file path
            pattern: File pattern to match (e.g., "chunk_*.txt")
            separator: Separator between chunks
        
        Returns:
            True if successful
        """
        try:
            parts_dir = Path(parts_dir)
            if not parts_dir.exists():
                self.logger.error(f"Parts directory not found: {parts_dir}")
                return False
            
            # Get all matching files, sorted
            chunk_files = sorted(parts_dir.glob(pattern))
            
            if not chunk_files:
                self.logger.warning(f"No files found matching pattern: {pattern}")
                return False
            
            self.logger.info(f"Combining {len(chunk_files)} chunks...")
            
            # Combine content
            combined_content = []
            for chunk_file in chunk_files:
                try:
                    content = chunk_file.read_text(encoding='utf-8')
                    combined_content.append(content)
                except Exception as e:
                    self.logger.error(f"Error reading {chunk_file.name}: {e}")
                    return False
            
            # Write combined file
            output_file = Path(output_file)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            final_content = separator.join(combined_content)
            output_file.write_text(final_content, encoding='utf-8')
            
            self.logger.info(f"✅ Combined file created: {output_file}")
            self.logger.info(f"   Total size: {len(final_content):,} characters")
            
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to combine chunks: {e}", exc_info=True)
            return False
    
    def archive_chunks(
        self,
        parts_dir: Path,
        archive_name: str = "archived_parts"
    ) -> bool:
        """
        Archive processed chunks to archive directory.
        
        Args:
            parts_dir: Directory containing parts
            archive_name: Name for archive subdirectory
        
        Returns:
            True if successful
        """
        try:
            parts_dir = Path(parts_dir)
            if not parts_dir.exists():
                return False
            
            # Create archive directory
            parent = parts_dir.parent
            archive_dir = parent / archive_name
            
            if archive_dir.exists():
                shutil.rmtree(archive_dir)
            
            # Move parts to archive
            shutil.move(str(parts_dir), str(archive_dir))
            
            self.logger.info(f"✅ Chunks archived to: {archive_dir}")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to archive chunks: {e}")
            return False
    
    def read_file(self, file_path: Path, encoding: str = 'utf-8') -> Optional[str]:
        """
        Read text file with error handling.
        
        Args:
            file_path: Path to file
            encoding: File encoding
        
        Returns:
            File content or None if failed
        """
        try:
            return Path(file_path).read_text(encoding=encoding)
        except Exception as e:
            self.logger.error(f"Failed to read {file_path}: {e}")
            return None
    
    def write_file(
        self,
        file_path: Path,
        content: str,
        encoding: str = 'utf-8'
    ) -> bool:
        """
        Write text file with error handling.
        
        Args:
            file_path: Path to file
            content: Content to write
            encoding: File encoding
        
        Returns:
            True if successful
        """
        try:
            file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding=encoding)
            return True
        except Exception as e:
            self.logger.error(f"Failed to write {file_path}: {e}")
            return False
