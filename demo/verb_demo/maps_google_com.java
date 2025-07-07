import com.google.gson.JsonObject;
import com.microsoft.playwright.BrowserContext;

public interface maps_google_com {
    /**
     * Get directions between two locations
     * @param source The starting location
     * @param destination The destination location
     * @return JsonObject containing travel_time, distance, and route information
     */
    JsonObject get_direction(String source, String destination);
    
        /**
     * This method retrieves a list of nearby businesses based on a reference point and business description.
     * 
     * @param referencePoint The location from which to find nearby businesses (e.g., "Seattle, WA").
     * @param businessDescription A description of the type of business to search for (e.g., "coffee shop").
     * @param maxCount The maximum number of businesses to return.
     * @return A list of of the nearest businesses. Each business info contains a "name" property and an "address" property.
     */
    JsonObject get_nearestBusinesses(String referencePoint, String businessDescription, int maxCount);
}
