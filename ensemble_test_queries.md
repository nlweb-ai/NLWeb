# Ensemble Tool Test Queries

The ensemble tool is now re-enabled and ready for testing. Here are some example queries that should trigger the ensemble tool:

## Meal Planning Queries
1. "Give me an appetizer, main and dessert for an Asian fusion dinner"
2. "Plan a complete Italian meal with starter, pasta, and dessert"
3. "Suggest a three-course vegan dinner menu"
4. "Create a romantic dinner with appetizer, entree, and dessert"
5. "What should I serve for a Mexican-themed dinner party - appetizer, main, and dessert?"

## Travel Itinerary Queries
1. "I am spending a few hours in Barcelona. Give some museums I can go to and nearby restaurants"
2. "Plan a day in Paris with attractions and places to eat"
3. "What museums and cafes should I visit in Amsterdam?"
4. "Suggest things to do and where to eat in Tokyo for a weekend"
5. "Give me tourist spots and restaurants for a day trip to San Francisco"

## Outfit/Gear Recommendations
1. "Suggest the right footwear, jacket, etc. for hiking in the Grand Canyon in January"
2. "What should I wear for skiing in Colorado - jacket, pants, and accessories?"
3. "Recommend running gear for marathon training in summer"
4. "What clothing and gear do I need for camping in fall?"
5. "Suggest an outfit for a beach vacation - swimwear, cover-up, and accessories"

## Event Planning
1. "Plan a romantic date night with dinner, activity, and dessert"
2. "Suggest a birthday party with venue, food, and entertainment options"
3. "Plan a corporate event with location, catering, and team activities"
4. "What should I plan for a baby shower - venue, food, and games?"
5. "Organize a weekend getaway with hotel, activities, and dining"

## How to Test

1. Make sure the server is running
2. Try these queries in the web interface
3. Watch the console output to see:
   - All tool scores being printed
   - The ensemble tool should score high (80-100) for these queries
   - The search tool should score lower
   - FastTrack should be aborted when ensemble is selected

## Expected Behavior

When the ensemble tool is selected:
- Multiple parallel searches will be executed based on the query
- Results will be combined into a cohesive recommendation
- The response will show related items that work well together