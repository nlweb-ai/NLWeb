import com.google.gson.JsonArray;
import com.microsoft.playwright.BrowserContext;

/**
 * YouTube video search interface
 * Provides methods to search for videos on YouTube
 */
public interface youtube_com {
    /**
     * Search YouTube for a query and return the top 5 video titles, durations, and URLs
     * @param query The search query (e.g., "quantum physics")
     * @return JsonArray of video info objects with keys: "title", "length", "url"
     */
    JsonArray searchVideos(String query);
}
