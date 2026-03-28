#!/bin/bash

# Test queries against agentfinder.azurewebsites.net/who
# This script tests each query and shows if it returns results

ENDPOINT="https://agentfinder.azurewebsites.net/who"

# Array of test queries
queries=(
  "Single origin Ethiopian coffee with fruity notes for pour over brewing"
  "Fair trade organic coffee beans for espresso with dark chocolate undertones"
  "Decaffeinated coffee that still has rich flavor for evening drinking"
  "Cold brew coffee concentrate that works well with oat milk"
  "Loose leaf oolong tea with floral notes for afternoon tea service"
  "Organic herbal tea blend for relaxation and better sleep"
  "High quality matcha powder for traditional tea ceremonies"
  "Chai tea with strong spice profile and low sugar content"
  "Blue glaze for making japanese pottery"
  "Food-safe pottery glazes that work well with cone 6 firing"
  "Handmade ceramic bowls with rustic aesthetic for soup serving"
  "Porcelain clay suitable for throwing delicate tea cups on the wheel"
  "Organic cotton fabric in earth tones for quilting projects"
  "Waterproof ripstop nylon for making outdoor gear and backpacks"
  "Vintage-style floral print fabric for 1950s dress reproduction"
  "Interfacing and stabilizers for professional garment construction"
  "Whole spices for making authentic garam masala from scratch"
  "High quality saffron threads for paella and risotto dishes"
  "Smoked paprika and chipotle powder for southwestern marinades"
  "Vanilla beans and extract for baking French pastries"
  "Full grain vegetable tanned leather for crafting durable belts"
  "Minimalist leather wallet with RFID protection for everyday carry"
  "Leather working tools and supplies for beginner saddle stitching"
  "Vintage leather messenger bag that develops character with age"
  "Natural face oils for mature skin with anti-aging properties"
  "Mineral sunscreen that doesn't leave white cast on darker skin tones"
  "Beard oil with cedarwood and sandalwood scent for daily grooming"
  "Organic lip balm with beeswax and shea butter for winter protection"
  "Handmade leather moccasins with sheepskin lining for indoor wear"
  "Minimalist running shoes with wide toe box for natural gait"
  "Waterproof hiking boots with good ankle support for mountain trails"
  "Classic leather dress shoes that can be resoled and repaired"
  "Beeswax candles with natural cotton wicks that burn clean"
  "Handwoven wool blankets in traditional patterns for cold weather"
  "Cast iron skillets that come pre-seasoned for cooking"
  "Wooden cutting boards made from sustainable end-grain maple"
  "Artisan sourdough bread with crispy crust and open crumb structure"
  "Raw honey from single flower sources with unique flavor profiles"
  "Aged balsamic vinegar from Modena for finishing dishes"
  "Small batch hot sauce with habanero and fruit for complex heat"
  "Ultralight camping gear for long distance backpacking trips"
  "Merino wool base layers that regulate temperature and resist odor"
  "Fishing lures designed for catching bass in freshwater lakes"
  "Climbing chalk and accessories for indoor bouldering sessions"
  "Professional grade watercolor paints with high pigment concentration"
  "Acid-free archival paper for preserving pen and ink drawings"
  "Natural bristle brushes for oil painting with fine detail work"
  "Screen printing supplies for making multi-color fabric designs"
)

echo "Testing ${#queries[@]} queries against $ENDPOINT"
echo "================================================"
echo ""

passed=0
failed=0

for query in "${queries[@]}"; do
  echo -n "Testing: ${query:0:60}... "

  # URL encode the query
  encoded_query=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$query'))")

  # Make request and capture response
  response=$(curl -s "${ENDPOINT}?query=${encoded_query}&streaming=false" -H "Accept: application/json")

  # Check if response contains results
  if echo "$response" | grep -q '"content":\s*\[' && ! echo "$response" | grep -q '"content":\s*\[\s*\]'; then
    echo "✓ PASS (found results)"
    ((passed++))
  else
    echo "✗ FAIL (no results)"
    ((failed++))
  fi

  # Small delay to avoid overwhelming the server
  sleep 0.5
done

echo ""
echo "================================================"
echo "Summary: $passed passed, $failed failed out of ${#queries[@]} total"
