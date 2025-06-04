-- Sample script to load the datasets in the data/ directory into Snowflake Cortex Search services.
-- The Snowflake Cortex Search service will embed the data and use a mixture of vector and traditional information retrieval
-- techniques and ranking to return the most relevant results for a query.
--
-- The following statements can be run in a Snowflake Worksheet or via the Snowflake command-line interface
-- https://docs.snowflake.com/en/developer-guide/snowflake-cli/index
--
-- For example (replace all $FOO variables with appropriate values):
-- Where CONNECTION is something configured via https://docs.snowflake.com/en/developer-guide/snowflake-cli/connecting/configure-connections
--
-- snow sql -f snowflake.sql  -D DATA_DIR=$(git rev-parse --show-toplevel)/data -D WAREHOUSE=$WAREHOUSE -c $CONNECTION

USE WAREHOUSE <% WAREHOUSE %>;
-- Copy the data file into Snowflake temporarily
PUT file://<% DATA_DIR %>/json/scifi_movies_schemas.txt @~/dataset OVERWRITE=TRUE;
-- Create a table from it
CREATE OR REPLACE TABLE SCIFI_MOVIES(URL STRING, SCHEMA_JSON STRING);
COPY INTO SCIFI_MOVIES
FROM @~/dataset
FILE_FORMAT = (TYPE = 'CSV' FIELD_DELIMITER='\t');

-- Index into a cortex search service
-- Could create a new search service for each site,
-- or a single service with all sites.
CREATE OR REPLACE CORTEX SEARCH SERVICE NLWEB_SAMPLE
ON SCHEMA_JSON
ATTRIBUTES URL, SITE
TARGET_LAG='1 hour'
WAREHOUSE=<% WAREHOUSE %>
AS SELECT URL, SCHEMA_JSON, 'scifi_movies' AS SITE FROM SCIFI_MOVIES;
