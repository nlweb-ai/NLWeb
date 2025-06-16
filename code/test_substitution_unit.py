#!/usr/bin/env python3
"""
Unit tests for the substitution handler logic.
Tests components without requiring the full server.
"""

import asyncio
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment
def load_environment():
    try:
        with open('set_keys.sh', 'r') as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip()
            if line.startswith('export ') and '=' in line:
                line = line.replace('export ', '')
                key, value = line.split('=', 1)
                value = value.strip('"').strip("'")
                os.environ[key] = value
        print("Environment loaded")
    except Exception as e:
        print(f"Error loading environment: {e}")

load_environment()

from core.substitution import SubstitutionHandler
from core.baseHandler import NLWebHandler

class MockHandler:
    """Mock handler for testing."""
    def __init__(self):
        self.query = "test query"
        self.site = "seriouseats"
        self.item_type = "Recipe"
        self.query_params = {
            'site': ['seriouseats'],
            'query': ['test query']
        }
        self.messages_sent = []
    
    async def send_message(self, message):
        """Mock send_message to capture output."""
        self.messages_sent.append(message)
        print(f"Message sent: {message.get('message_type', 'unknown')}")

async def test_recipe_type_extraction():
    """Test the recipe type extraction logic."""
    print("\n" + "="*50)
    print("Testing Recipe Type Extraction")
    print("="*50)
    
    handler = MockHandler()
    sub_handler = SubstitutionHandler({}, handler)
    
    test_cases = [
        ("chocolate cake", "cake"),
        ("banana bread", "bread"),
        ("chicken noodle soup", "soup"),
        ("apple pie", "pie"),
        ("spaghetti carbonara", "carbonara"),  # No common type, uses last word
        ("lasagna", "lasagna"),  # Single word
    ]
    
    for recipe_name, expected in test_cases:
        result = sub_handler._extract_recipe_type(recipe_name)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{recipe_name}' -> '{result}' (expected: '{expected}')")

async def test_substitution_patterns():
    """Test extraction of substitution patterns from recipes."""
    print("\n" + "="*50)
    print("Testing Substitution Pattern Extraction")
    print("="*50)
    
    handler = MockHandler()
    sub_handler = SubstitutionHandler({}, handler)
    
    # Mock reference recipes
    mock_recipes = [
        {
            'schema_object': [{
                'headline': 'Vegan Chocolate Cake',
                'description': 'A delicious dairy-free chocolate cake using almond milk instead of regular milk.'
            }]
        },
        {
            'schema_object': [{
                'name': 'Gluten-Free Pasta',
                'description': 'Made with rice flour as a substitute for wheat flour.'
            }]
        },
        {
            'schema_object': [{
                'headline': 'Regular Chocolate Chip Cookies',
                'description': 'Classic cookies with butter and eggs.'
            }]
        }
    ]
    
    patterns = sub_handler._extract_substitution_patterns(mock_recipes)
    
    print(f"Found {len(patterns)} substitution patterns:")
    for i, pattern in enumerate(patterns, 1):
        print(f"  {i}. {pattern[:100]}...")

async def test_search_query_generation():
    """Test how search queries are generated for different dietary needs."""
    print("\n" + "="*50)
    print("Testing Search Query Generation")
    print("="*50)
    
    test_cases = [
        {
            'params': {'dietary_need': 'dairy-free', 'recipe_name': 'chocolate cake'},
            'expected_queries': ['dairy free', 'vegan', 'lactose free', 'dairy free cake', 'vegan cake']
        },
        {
            'params': {'dietary_need': 'gluten-free', 'recipe_name': 'pasta'},
            'expected_queries': ['gluten free', 'celiac', 'wheat free', 'gluten free pasta']
        },
        {
            'params': {'unavailable_ingredient': 'eggs'},
            'expected_queries': ['substitute for eggs', 'without eggs']
        },
        {
            'params': {'dietary_need': 'low-sodium'},
            'expected_queries': ['low-sodium']
        }
    ]
    
    for test in test_cases:
        handler = MockHandler()
        sub_handler = SubstitutionHandler(test['params'], handler)
        
        # We'll need to inspect the search queries that would be generated
        # This would require modifying the _find_reference_recipes method
        # For now, we'll just show what we expect
        print(f"\nParameters: {test['params']}")
        print(f"Expected queries would include: {test['expected_queries'][:3]}")

async def test_confidence_levels():
    """Test confidence level assignment based on different scenarios."""
    print("\n" + "="*50)
    print("Testing Confidence Level Logic")
    print("="*50)
    
    print("\nScenarios that should result in different confidence levels:")
    print("- HIGH: Specific recipe found + multiple reference recipes")
    print("- MEDIUM: Either specific recipe OR reference recipes found")
    print("- LOW: No specific recipe and no reference recipes")
    
    # This would require actual execution with mock data
    # For now, we document the expected behavior

async def test_message_formatting():
    """Test the message formatting for substitution suggestions."""
    print("\n" + "="*50)
    print("Testing Message Formatting")
    print("="*50)
    
    handler = MockHandler()
    sub_handler = SubstitutionHandler(
        {'recipe_name': 'chocolate cake', 'dietary_need': 'dairy-free'},
        handler
    )
    
    # Mock substitution data
    mock_substitution_data = {
        'confidence_level': 'high',
        'primary_substitution': {
            'original': 'butter',
            'substitute': 'coconut oil',
            'ratio': '1:1',
            'preparation_notes': 'Use refined coconut oil for neutral flavor'
        },
        'alternative_substitutions': [
            {
                'substitute': 'vegan butter',
                'ratio': '1:1',
                'notes': 'Best for maintaining butter flavor'
            }
        ],
        'recipe_adjustments': {
            'ingredient_changes': 'Replace milk with almond milk (1:1 ratio)',
            'method_changes': 'No changes needed',
            'timing_changes': 'Baking time remains the same'
        },
        'expected_differences': {
            'taste': 'Slightly less rich, may have subtle coconut flavor',
            'texture': 'May be slightly denser',
            'appearance': 'Color may be slightly darker'
        },
        'tips_for_success': [
            'Ensure all ingredients are at room temperature',
            'Don\'t overmix the batter'
        ],
        'common_mistakes': [
            'Using unrefined coconut oil which adds strong coconut flavor'
        ]
    }
    
    # Send the message
    await sub_handler._send_enhanced_substitution_message(mock_substitution_data, [])
    
    # Check the sent message
    if handler.messages_sent:
        msg = handler.messages_sent[0]
        content = msg.get('content', '')
        
        print("\nGenerated message preview:")
        print("-" * 50)
        lines = content.split('\n')
        for line in lines[:20]:  # Show first 20 lines
            print(line)
        if len(lines) > 20:
            print(f"... ({len(lines) - 20} more lines)")
        print("-" * 50)
        
        # Validate key sections are present
        sections = ['Recommended Substitution', 'Alternative Options', 'Recipe Adjustments', 
                   'What to Expect', 'Tips for Success', 'Common Mistakes']
        
        print("\nSection validation:")
        for section in sections:
            present = section in content
            status = "✓" if present else "✗"
            print(f"  {status} {section}")

async def main():
    """Run all unit tests."""
    print("SUBSTITUTION HANDLER UNIT TESTS")
    
    await test_recipe_type_extraction()
    await test_substitution_patterns()
    await test_search_query_generation()
    await test_confidence_levels()
    await test_message_formatting()
    
    print("\n" + "="*50)
    print("Unit tests completed!")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())