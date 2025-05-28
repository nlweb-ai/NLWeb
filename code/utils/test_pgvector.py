#!/usr/bin/env python3
# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Test script for pgvector with psycopg3
This script verifies that the pgvector extension works correctly with psycopg3
"""

import asyncio
import psycopg
import pgvector.psycopg
import numpy as np
from psycopg_pool import AsyncConnectionPool

async def test_pgvector():
    """Test pgvector with psycopg3"""
    print("\n=== pgvector with psycopg3 Test ===\n")
    
    # Connection string - replace with your actual connection details
    conninfo = "postgresql://username:password@localhost:5432/database"
    
    # Test with environment variable
    import os
    if "POSTGRES_CONNECTION_STRING" in os.environ:
        conninfo = os.environ["POSTGRES_CONNECTION_STRING"]
        print(f"Using connection string from POSTGRES_CONNECTION_STRING")
    else:
        print("WARNING: POSTGRES_CONNECTION_STRING environment variable not found")
        print("Please set POSTGRES_CONNECTION_STRING or update the script with your connection details")
        print("Example: postgresql://username:password@localhost:5432/database")
        return
    
    print("Connecting to PostgreSQL...")
    pool = AsyncConnectionPool(conninfo=conninfo, min_size=1, max_size=5, open=False)
    # Explicitly open the pool as recommended in newer psycopg versions
    await pool.open()
    
    try:
        async with pool.connection() as conn:
            # Register vector type
            await pgvector.psycopg.register_vector_async(conn)
            
            print("Connection established!")
            
            # Check pgvector extension
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM pg_extension WHERE extname = 'vector'")
                row = await cur.fetchone()
                
                if not row:
                    print("ERROR: pgvector extension not installed in the database")
                    print("Please install the pgvector extension before continuing")
                    return
                
                print("pgvector extension is installed")
                
                # Test creating a vector
                print("\nTesting vector operations...")
                
                # Create test table if not exists
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS pgvector_test (
                        id SERIAL PRIMARY KEY,
                        embedding vector(3) NOT NULL
                    )
                """)
                
                # Insert a test vector
                test_vector = [1.0, 2.0, 3.0]
                await cur.execute(
                    "INSERT INTO pgvector_test (embedding) VALUES (%s) RETURNING id",
                    (test_vector,)
                )
                
                id_row = await cur.fetchone()
                test_id = id_row[0]
                print(f"Inserted test vector with ID: {test_id}")
                
                # Retrieve the vector
                await cur.execute(
                    "SELECT embedding FROM pgvector_test WHERE id = %s",
                    (test_id,)
                )
                
                result = await cur.fetchone()
                retrieved_vector = result[0]
                
                print(f"Retrieved vector: {retrieved_vector}")
                
                # Clean up
                await cur.execute("DROP TABLE pgvector_test")
                print("Test table dropped")
                
                print("\nTest completed successfully!")
    
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Close the connection pool
        await pool.close()
        print("Connection pool closed")

if __name__ == "__main__":
    asyncio.run(test_pgvector())
