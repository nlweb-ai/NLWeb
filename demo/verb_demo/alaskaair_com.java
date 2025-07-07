import com.google.gson.JsonObject;
import com.microsoft.playwright.BrowserContext;

public interface alaskaair_com {
    /**
     * Search for flights between origin and destination
     * @param origin Origin airport code
     * @param destination Destination airport code
     * @param outboundDate Outbound flight date
     * @param returnDate Return flight date
     * @return JsonObject containing flight information
     */
    JsonObject searchFlights(String origin, String destination, String outboundDate, String returnDate);
}
