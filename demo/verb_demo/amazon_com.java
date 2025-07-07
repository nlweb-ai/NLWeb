import com.google.gson.JsonObject;
import com.microsoft.playwright.BrowserContext;

public interface amazon_com {
    /**
     * Clear all items from the shopping cart
     */
    void clearCart();
    
    /**
     * Add an item to the cart and return cart information
     * @param item The item to search for and add to cart
     * @return JsonObject containing cart information with item names and prices
     */
    JsonObject addItemToCart(String item);
}
