import java.io.IOException;
import java.util.List;

public interface OpenLibrary {
    /**
     * Search for books by title
     * @param title Book title to search for
     * @param limit Maximum number of results to return
     * @return List of book information
     */
    public List<String> search(String q, String fields, String sort, String lang, int limit, int page) throws IOException, InterruptedException;
    
    /**
     * Search for authors by name
     * @param authorName Author name to search for
     * @param limit Maximum number of results to return
     * @return List of author information
     */
    List<String> searchAuthors(String authorName, Integer limit) throws IOException, InterruptedException;
    
    /**
     * Get works and information for a subject with details
     * @param subject The subject name (e.g., "love", "science", "history")
     * @param details Whether to include detailed information (authors, publishers, etc.)
     * @return List of subject information and sample works
     */
    public List<String> getSubject(String subject, boolean details) throws IOException, InterruptedException;
}
