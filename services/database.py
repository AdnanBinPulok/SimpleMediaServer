import os
import aiosqlite
from pathlib import Path
import traceback
import asyncio
from contextlib import asynccontextmanager
import datetime

# Setup logging
from services.logging import logger

# Global database configuration
DB_PATH = Path("./data/database.db")
MAX_CONNECTIONS = 50

# Connection pool implementation
class DatabaseConnectionPool:
    def __init__(self, max_connections=MAX_CONNECTIONS):
        self.max_connections = max_connections
        self.connections = []
        self.semaphore = asyncio.Semaphore(max_connections)
        self.initialized = False
    
    async def initialize(self):
        """Initialize the database and connection pool"""
        if not DB_PATH.exists():
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            DB_PATH.touch()
            logger.info(f"Database created at {DB_PATH}")
        else:
            logger.info(f"Database already exists at {DB_PATH}")
        
        self.initialized = True
    
    async def acquire(self):
        """Get a connection from the pool or create a new one"""
        if not self.initialized:
            await self.initialize()
            
        await self.semaphore.acquire()
        
        try:
            # Try to reuse an existing connection
            if self.connections:
                connection = self.connections.pop()
            else:
                connection = await aiosqlite.connect(str(DB_PATH))
                # Enable foreign keys
                await connection.execute("PRAGMA foreign_keys = ON")
                # Row factory for dict-like access
                connection.row_factory = aiosqlite.Row
                
            return connection
        except Exception as e:
            # Release semaphore on error
            self.semaphore.release()
            logger.error(f"Error acquiring database connection: {traceback.format_exc()}")
            raise
    
    async def release(self, connection):
        """Return a connection to the pool"""
        if connection:
            try:
                # Keep the connection open for reuse
                self.connections.append(connection)
            except Exception as e:
                logger.error(f"Error returning connection to pool: {traceback.format_exc()}")
                try:
                    await connection.close()
                except:
                    pass
            finally:
                self.semaphore.release()

# Create global connection pool
pool = DatabaseConnectionPool()

@asynccontextmanager
async def get_connection():
    """Context manager for database connections"""
    connection = None
    try:
        connection = await pool.acquire()
        yield connection
    finally:
        if connection:
            await pool.release(connection)

class FilesTable:
    def __init__(self) -> None:
        self.table_name = "files"
    
    async def create_table(self) -> None:
        async with get_connection() as conn:
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL UNIQUE,
                    storage_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    file_size INTEGER DEFAULT 0,
                    access_count INTEGER DEFAULT 0,
                    last_accessed TIMESTAMP DEFAULT NULL,
                    expires_at TIMESTAMP DEFAULT NULL,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Create index for faster lookups
            await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_file_path ON {self.table_name} (file_path)")
            await conn.commit()
            logger.info(f"Table {self.table_name} created or already exists")
    
    async def add_new_file(self, file_path: str, storage_path: str, file_name: str, 
                          file_type: str, file_size: int = 0,uploaded_at: str = datetime.datetime.now(datetime.timezone.utc),expires_at: str = None) -> int:
        """Add a new file and return its ID"""
        async with get_connection() as conn:
            cursor = await conn.execute(f"""
                INSERT INTO {self.table_name} 
                (file_path, storage_path, file_name, file_type, file_size, uploaded_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (file_path, storage_path, file_name, file_type, file_size, uploaded_at, expires_at))
            await conn.commit()
            logger.info(f"File {file_path} added to {self.table_name}")
            return cursor.lastrowid

    async def get_file_by_id(self, file_id: int) -> dict:
        """Get file by ID"""
        async with get_connection() as conn:
            cursor = await conn.execute(f"""
                SELECT * FROM {self.table_name} WHERE id = ?
            """, (file_id,))
            file_data = await cursor.fetchone()
            
            if file_data:
                logger.info(f"File with ID {file_id} retrieved from {self.table_name}")
                return dict(file_data)
            
            logger.warning(f"File with ID {file_id} not found in {self.table_name}")
            return None

    async def get_file(self, file_path: str) -> dict:
        async with get_connection() as conn:
            cursor = await conn.execute(f"""
                SELECT * FROM {self.table_name} WHERE file_path = ?
            """, (file_path,))
            file_data = await cursor.fetchone()
            
            if file_data:
                # Update access count atomically
                await conn.execute(f"""
                    UPDATE {self.table_name}
                    SET access_count = access_count + 1, last_accessed = CURRENT_TIMESTAMP
                    WHERE file_path = ?
                """, (file_path,))
                await conn.commit()
                logger.info(f"File {file_path} retrieved from {self.table_name}")
                return dict(file_data)
            
            logger.warning(f"File {file_path} not found in {self.table_name}")
            return None

    async def delete_file(self, file_path: str) -> bool:
        """Delete a file and return True if deleted"""
        async with get_connection() as conn:
            cursor = await conn.execute(f"""
                DELETE FROM {self.table_name} WHERE file_path = ?
            """, (file_path,))
            await conn.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"File {file_path} deleted from {self.table_name}")
                return True
            
            logger.warning(f"File {file_path} not found for deletion")
            return False
    
    async def get_all_files(self, limit: int = 100, offset: int = 0) -> list:
        """Get all files with pagination"""
        async with get_connection() as conn:
            cursor = await conn.execute(f"""
                SELECT * FROM {self.table_name}
                ORDER BY uploaded_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
            files_data = await cursor.fetchall()
            
            logger.info(f"{len(files_data)} files retrieved from {self.table_name}")
            return [dict(file) for file in files_data]

    async def count_all_by_file_type(self) -> dict:
        """Count files grouped by file type"""
        async with get_connection() as conn:
            cursor = await conn.execute(f"""
                SELECT file_type, COUNT(*) as count 
                FROM {self.table_name} 
                GROUP BY file_type
            """)
            results = await cursor.fetchall()
            
            counts = {row['file_type']: row['count'] for row in results}
            logger.info(f"File counts by type: {counts}")
            return counts
            
    async def clear_expired_files(self) -> int:
        """Delete expired files and return count of deleted files"""
        async with get_connection() as conn:
            cursor = await conn.execute(f"""
                DELETE FROM {self.table_name} 
                WHERE expires_at IS NOT NULL AND expires_at < CURRENT_TIMESTAMP
            """)
            await conn.commit()
            deleted_count = cursor.rowcount
            
            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} expired files")
            return deleted_count
    
    async def update_file_access(self, file_path: str) -> None:
        """Update access count and last accessed time for a file"""
        async with get_connection() as conn:
            await conn.execute(f"""
                UPDATE {self.table_name}
                SET access_count = access_count + 1, last_accessed = CURRENT_TIMESTAMP
                WHERE file_path = ?
            """, (file_path,))
            await conn.commit()
            logger.info(f"File {file_path} access updated")

    async def get_file_they_have_expired_at_not_null(self) -> list:
        """Get files with non-null expires_at"""
        async with get_connection() as conn:
            cursor = await conn.execute(f"""
                SELECT * FROM {self.table_name} WHERE expires_at IS NOT NULL
            """)
            files_data = await cursor.fetchall()
            
            logger.info(f"{len(files_data)} files with non-null expires_at retrieved")
            return [dict(file) for file in files_data]


# Create singleton instance
files_db = FilesTable()

async def initDatabase():
    """Initialize database and tables"""
    await pool.initialize()
    await files_db.create_table()
    # Add more table initializations here if needed
    logger.info("Database initialized successfully")


async def closeDatabase():
    """Close all database connections"""
    for conn in pool.connections:
        try:
            await conn.close()
        except:
            pass
    pool.connections.clear()
    logger.info("All database connections closed")