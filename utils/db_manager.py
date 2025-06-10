import chromadb
import shutil
import os
import logging
import time
import gc
from typing import Optional

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Handle ChromaDB initialization and cleanup"""
    
    def __init__(self, db_dir: str):
        self.db_dir = db_dir
        self.client: Optional[chromadb.Client] = None
        self._ensure_directory()
    
    def _ensure_directory(self):
        """Ensure clean database directory"""
        try:
            # Remove existing directory completely
            if os.path.exists(self.db_dir):
                shutil.rmtree(self.db_dir, ignore_errors=True)
                time.sleep(0.5)  # Wait for cleanup
            os.makedirs(self.db_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"Directory setup failed: {str(e)}")
            raise
    
    def initialize(self) -> bool:
        """Initialize ChromaDB client with proper cleanup and configuration"""
        try:
            # Close any existing client and force cleanup
            self.close()
            gc.collect()
            
            # Use a simpler client configuration
            settings = chromadb.Settings(
                is_persistent=True,
                persist_directory=self.db_dir,
                anonymized_telemetry=False
            )
            
            # Create new client
            self.client = chromadb.PersistentClient(
                path=self.db_dir,
                settings=settings
            )

            # Delete existing collection if it exists
            try:
                self.client.delete_collection("documents")
                logger.info("Deleted existing collection")
            except:
                pass  # Collection may not exist
            
            # Create fresh collection
            self.collection = self.client.create_collection(
                name="documents",
                metadata={"hnsw:space": "cosine"}
            )
            
            logger.info("Successfully initialized ChromaDB")
            return True
            
        except Exception as e:
            logger.error(f"ChromaDB initialization failed: {str(e)}")
            return False
            
    def close(self):
        """Ensure proper client cleanup"""
        if self.client:
            try:
                self.client.persist()
            except:
                pass
            finally:
                self.client = None
                gc.collect()

    def reset_database(self) -> bool:
        """Reset database with proper cleanup"""
        try:
            # Close any existing client
            self.close()
            
            # Remove existing directory
            if os.path.exists(self.db_dir):
                tries = 3
                while tries > 0:
                    try:
                        shutil.rmtree(self.db_dir, ignore_errors=True)
                        break
                    except Exception:
                        tries -= 1
                        time.sleep(1)
                        gc.collect()
            
            # Create fresh directory
            os.makedirs(self.db_dir, exist_ok=True)
            
            # Initialize new client
            return self.initialize()
            
        except Exception as e:
            logger.error(f"Database reset failed: {str(e)}")
            return False

    def __del__(self):
        """Ensure cleanup on object destruction"""
        self.close()
