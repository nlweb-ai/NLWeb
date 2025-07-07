import com.google.gson.JsonArray;
import com.microsoft.playwright.BrowserContext;

/**
 * Redfin apartment search interface
 * Provides methods to search for rental apartments
 */
public interface redfin_com {
    /**
     * Search Redfin for apartments for rent in a location and price range
     * @param location The city or area to search (e.g., "bellevue, WA")
     * @param minRent The minimum rent (e.g., 2000)
     * @param maxRent The maximum rent (e.g., 3000)
     * @return JsonArray of apartment info objects with keys: "title", "price", "address", "url"
     */
    JsonArray searchApartments(String location, int minRent, int maxRent);
}
