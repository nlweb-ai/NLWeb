import com.google.gson.JsonObject;

public interface costco_com {
    /**
     * Search for a list of products at Costco and return the list.
     * @param searchTerm The product to search for (e.g., "eggs", "mower").
     * @return JsonObject with keys: "product_name", "product_price" (if found)
     */
    JsonObject searchProducts(String searchTerm);
    
    /**
     * Set the preferred warehouse by city or zip code
     * @param location The city, state, or zip code to set as preferred warehouse
     * @return JsonObject with status
     */
    JsonObject setPreferredWarehouse(String location);
}
