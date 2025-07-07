import java.util.List;

public interface Spotify {
    /**
     * Search for tracks
     * @param query Search query
     * @param market Market/country code
     * @param limit Maximum number of results
     * @return List of track information
     */
    List<String> searchTracks(String query, String market, Integer limit);
    
    /**
     * Search for artists
     * @param query Search query
     * @param market Market/country code
     * @param limit Maximum number of results
     * @return List of artist information
     */
    List<String> searchArtists(String query, String market, Integer limit);
    
    /**
     * Search for albums
     * @param query Search query
     * @param market Market/country code
     * @param limit Maximum number of results
     * @return List of album information
     */
    List<String> searchAlbums(String query, String market, Integer limit);
    
    /**
     * Search for playlists
     * @param query Search query
     * @param market Market/country code
     * @param limit Maximum number of results
     * @return List of playlist information
     */
    List<String> searchPlaylists(String query, String market, Integer limit);
    
    /**
     * General search method
     * @param query Search query
     * @param type Search type (track, artist, album, playlist)
     * @return List of search results
     */
    List<String> search(String query, String type);
    
}
