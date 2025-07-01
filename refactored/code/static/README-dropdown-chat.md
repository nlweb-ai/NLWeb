# NLWeb Dropdown Chat Component

A standalone, embeddable search box with integrated chat functionality. Easily add natural language search with conversation history to any webpage with just a few lines of code.

## Features

- 🔍 **Natural Language Search** - Users can search using conversational queries
- 💬 **Dropdown Chat Interface** - Clean dropdown UI that appears below the search box
- 📝 **Conversation History** - Persistent conversation storage with site-specific filtering
- 🔄 **Follow-up Questions** - Support for contextual follow-up queries
- 🎨 **Customizable** - Easy to style and configure
- 📦 **Self-contained** - Minimal dependencies, works out of the box
- 🚀 **Multiple Instances** - Support for multiple search boxes on the same page

## Quick Start

### 1. Include the Files

```html
<!-- Include CSS -->
<link rel="stylesheet" href="nlweb-dropdown-chat.css">

<!-- Include JavaScript -->
<script type="module">
  import { NLWebDropdownChat } from './nlweb-dropdown-chat.js';
</script>
```

### 2. Add a Container

```html
<div id="my-search-container"></div>
```

### 3. Initialize

```javascript
const chat = new NLWebDropdownChat({
  containerId: 'my-search-container',
  site: 'seriouseats',
  placeholder: 'Search for recipes...'
});
```

That's it! You now have a fully functional search box with chat capabilities.

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `containerId` | string | 'nlweb-search-container' | ID of the container element |
| `site` | string | 'all' | Site to search (filters conversations) |
| `placeholder` | string | 'Ask a question...' | Search input placeholder text |
| `endpoint` | string | window.location.origin | Base URL for the NLWeb API |
| `cssPrefix` | string | 'nlweb-dropdown' | CSS class prefix for styling |

## API Methods

### search(query)
Programmatically perform a search.
```javascript
chat.search('chocolate cake recipes');
```

### setQuery(query)
Set the search input value without searching.
```javascript
chat.setQuery('pasta recipes');
```

### setSite(site)
Change the site for searching.
```javascript
chat.setSite('epicurious');
```

### destroy()
Clean up the component and remove from DOM.
```javascript
chat.destroy();
```

## Advanced Usage

### Multiple Instances

You can have multiple search boxes on the same page with different configurations:

```javascript
// Recipe search
const recipeSearch = new NLWebDropdownChat({
  containerId: 'recipe-search',
  site: 'seriouseats',
  placeholder: 'Search for recipes...'
});

// Product search
const productSearch = new NLWebDropdownChat({
  containerId: 'product-search',
  site: 'amazon',
  placeholder: 'Search for products...'
});
```

### Custom Styling

Override the default styles by targeting the CSS classes:

```css
/* Custom search input */
.nlweb-dropdown-search-input {
  border: 1px solid #your-color;
  font-size: 18px;
}

/* Custom dropdown background */
.nlweb-dropdown-results {
  background-color: #f9f9f9;
}

/* Custom conversation items */
.nlweb-dropdown-conversation-item {
  padding: 15px;
  border-radius: 10px;
}
```

### Custom Endpoint

If your NLWeb server is hosted elsewhere:

```javascript
const chat = new NLWebDropdownChat({
  containerId: 'my-search',
  endpoint: 'https://api.yourserver.com'
});
```

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## Dependencies

The component requires these files from the NLWeb system:
- `fp-chat-interface.js`
- `json-renderer.js`
- `type-renderers.js`
- `recipe-renderer.js`

These are loaded automatically from the configured endpoint.

## File Structure

```
nlweb-dropdown-chat.js      # Main JavaScript module
nlweb-dropdown-chat.css     # Standalone styles
dropdown-integration-example.html  # Integration example
README-dropdown-chat.md     # This file
```

## Troubleshooting

### Search box not appearing
- Check that the container ID matches
- Ensure the container element exists in the DOM
- Check browser console for errors

### Conversations not persisting
- Conversations are stored in localStorage
- Check if localStorage is enabled
- Each site has separate conversation storage

### Styling conflicts
- Use the `cssPrefix` option to avoid conflicts
- Increase CSS specificity if needed
- Check that the CSS file is loaded

## License

[Your License Here]

## Contributing

[Your Contributing Guidelines Here]