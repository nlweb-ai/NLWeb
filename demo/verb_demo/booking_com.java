import com.google.gson.JsonObject;

public interface booking_com {
    /**
     * Search for hotels in a destination for given dates
     * @param destination The destination city/location
     * @param checkin_date Check-in date
     * @param checkout_date Check-out date
     * @return JsonObject containing hotel details. Each hotel is indexed as "hotel_x", which has the "hotelName" and "price" keys.
     */
    JsonObject search_hotel(String destination, String checkin_date, String checkout_date);
}
