import java.io.IOException;
import java.util.List;

/**
 * Wikimedia API interface for searching Wikipedia articles
 */
public interface Wikimedia {
    /**
     * Search for Wikipedia articles (matches the REST API endpoint name)
     * @param query The search query
     * @param languageCode Language code (e.g., "en" for English), optional
     * @param limit Number of results to return, optional
     * @return List of article titles
     */
    List<String> search(String query, String languageCode, int limit) throws IOException, InterruptedException;

    /**
     * Search for Wikipedia article titles that begin with the provided search terms (autocomplete)
     * Uses the search/title endpoint for title-based autocomplete functionality
     * @param query The search query - returns titles that begin with this text
     * @param languageCode Language code (e.g., "en" for English), defaults to "en" if null
     * @param limit Number of results to return (1-100), defaults to 5 if 0 or negative
     * @return List of article titles that begin with the search terms
     */
    List<String> searchTitles(String query, String languageCode, int limit) throws IOException, InterruptedException;

    /**
     * Get information about a specific Wikipedia page
     * Uses the page/{title}/bare endpoint to get page metadata
     * @param title The page title to get information for
     * @param languageCode Language code (e.g., "en" for English), defaults to "en" if null
     * @return List of page information (id, title, content model, license, html url, etc.)
     */
    List<String> getPage(String title, String languageCode) throws IOException, InterruptedException;

    /**
     * Get the HTML content of a specific Wikipedia page
     * Uses the page/{title}/html endpoint to get page HTML content
     * @param title The page title to get HTML content for
     * @param languageCode Language code (e.g., "en" for English), defaults to "en" if null
     * @return List of HTML content information (title, headings, statistics, etc.)
     */
    List<String> getHtml(String title, String languageCode) throws IOException, InterruptedException;

    /**
     * Create a new Wikipedia page (SIMULATION ONLY - does not actually create a page)
     * Uses the page endpoint with POST method to create new content
     * NOTE: This method only prints the request details and does not make actual API calls
     * to avoid real-world impact on Wikipedia
     * @param title The page title to create
     * @param source The page content/source in wikitext format
     * @param comment The edit comment explaining the page creation
     * @param contentModel The content model (e.g., "wikitext", "javascript", "css")
     * @param languageCode Language code (e.g., "en" for English), defaults to "en" if null
     * @return List of formatted request information showing what would be sent
     */
    List<String> createPage(String title, String source, String comment, String contentModel, String languageCode);

    /**
     * Edit an existing Wikipedia page (SIMULATION ONLY - does not actually edit a page)
     * Uses the page endpoint with PUT method to edit existing content
     * NOTE: This method only prints the request details and does not make actual API calls
     * to avoid real-world impact on Wikipedia
     * @param title The page title to edit
     * @param source The new page content/source in wikitext format
     * @param comment The edit comment explaining the changes
     * @param contentModel The content model (e.g., "wikitext", "javascript", "css")
     * @param latestRevisionId The latest revision ID for conflict detection
     * @param languageCode Language code (e.g., "en" for English), defaults to "en" if null
     * @return List of formatted request information showing what would be sent
     */
    List<String> editPage(String title, String source, String comment, String contentModel, long latestRevisionId, String languageCode);
}
