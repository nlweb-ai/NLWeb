import java.io.IOException;
import java.util.List;

/**
 * NASA API interface for various NASA services
 */
public interface Nasa {
    /**
     * Get Astronomy Picture of the Day (APOD)
     * @param date Date in YYYY-MM-DD format (optional, defaults to today)
     * @param hd Whether to retrieve high definition image
     * @return List of APOD data (title, url, explanation)
     */
    List<String> getApod(String date, boolean hd) throws IOException, InterruptedException;
    
    /**
     * Get Near Earth Objects feed by date range
     * @param startDate Start date in YYYY-MM-DD format
     * @param endDate End date in YYYY-MM-DD format (optional)
     * @return List of Near Earth Object data
     */
    List<String> getNeoFeed(String startDate, String endDate) throws IOException, InterruptedException;
    
    /**
     * Lookup a specific Near Earth Object by its NASA JPL small body ID
     * @param asteroidId The asteroid ID to lookup
     * @return List of Near Earth Object data for the specific asteroid
     */
    List<String> getNeoLookup(int asteroidId) throws IOException, InterruptedException;
    
    /**
     * Browse the overall Near Earth Objects dataset
     * @return List of Near Earth Object data from the browse endpoint
     */
    List<String> getNeoBrowse() throws IOException, InterruptedException;
    
}
