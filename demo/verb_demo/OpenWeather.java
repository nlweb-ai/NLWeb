import java.io.IOException;
import java.util.List;

public interface OpenWeather {
    /**
     * Get current weather by coordinates
     * @param lat Latitude
     * @param lon Longitude
     * @param units Temperature units (metric, imperial, kelvin)
     * @param lang Language for weather description
     * @return List of current weather information
     */
    List<String> getCurrentWeather(double lat, double lon, String units, String lang) throws IOException, InterruptedException;
        
    /**
     * Get 5-day weather forecast
     * @param lat Latitude
     * @param lon Longitude
     * @param units Temperature units
     * @param lang Language
     * @param cnt Number of forecast entries
     * @return List of forecast information
     */
    List<String> getForecast5Day(double lat, double lon, String units, String lang, Integer cnt) throws IOException, InterruptedException;
    
    /**
     * Get current air pollution data
     * @param lat Latitude
     * @param lon Longitude
     * @return List of air pollution information
     */
    List<String> getCurrentAirPollution(double lat, double lon) throws IOException, InterruptedException;
    
    /**
     * Get air pollution forecast
     * @param lat Latitude
     * @param lon Longitude
     * @return List of air pollution forecast
     */
    List<String> getAirPollutionForecast(double lat, double lon) throws IOException, InterruptedException;
    
    /**
     * Get historical air pollution data
     * @param lat Latitude
     * @param lon Longitude
     * @param start Start timestamp
     * @param end End timestamp
     * @return List of historical air pollution data
     */
    List<String> getHistoricalAirPollution(double lat, double lon, long start, long end) throws IOException, InterruptedException;
    
    /**
     * Get locations by name
     * @param query Location name query
     * @param limit Maximum number of results
     * @return List of location information
     */
    List<String> getLocationsByName(String query, Integer limit) throws IOException, InterruptedException;
    
    /**
     * Get location by ZIP code
     * @param zipCode ZIP code
     * @param countryCode Country code
     * @return List of location information
     */
    List<String> getLocationByZipCode(String zipCode, String countryCode) throws IOException, InterruptedException;
    
    /**
     * Get locations by coordinates
     * @param lat Latitude
     * @param lon Longitude
     * @param limit Maximum number of results
     * @return List of location information
     */
    List<String> getLocationsByCoordinates(double lat, double lon, Integer limit) throws IOException, InterruptedException;
}
