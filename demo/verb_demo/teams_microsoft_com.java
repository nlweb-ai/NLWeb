import com.google.gson.JsonObject;
import com.microsoft.playwright.BrowserContext;

public interface teams_microsoft_com {
    // /**
    //  * Send a message to a recipient via Microsoft Teams
    //  * @param recipientEmail The email address of the message recipient
    //  * @param messageText The text content of the message
    //  * @return JsonObject containing message information and status
    //  */
    // JsonObject sendMessage(String recipientEmail, String messageText);

    /**
     * Sends a message to a specified recipient in Microsoft Teams.
     * 
     * @param recipientEmail The email address of the recipient.
     * @param messageText The text of the message to send.
     * @return A JsonObject containing the recipient email, message text, and status.
     */
    JsonObject sendToGroupChat(String recipientEmail, String messageText);
}
