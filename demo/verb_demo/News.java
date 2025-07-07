import java.io.IOException;
import java.util.List;

public interface News {
    /**
     * Get news articles by query
     * @param query Search query for news articles
     * @return List of news article information
     */
    List<String> searchEverything(String q) throws IOException, InterruptedException;    
    /**
     * Get top headlines by category
     * @param category News category
     * @return List of top headlines
     */
    List<String> getTopHeadlines(String country, String category) throws IOException, InterruptedException;
}
