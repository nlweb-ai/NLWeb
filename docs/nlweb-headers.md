# NLWeb Response Headers

## Overview

NLWeb supports customizable response headers that can be configured to specify licensing, caching policies, UI rendering preferences, and other metadata. These headers are included with every API response to guide client applications in how to handle and display the data.

## Configuration

Response headers are configured in the `headers` section of `config_nlweb.yaml`. This allows instance administrators to define headers that apply to all responses from their NLWeb deployment.

## Common Use Cases

Based on the implementation in PR #205, headers use simple key names (not X-prefixed) and are sent as individual messages. Here are examples following the actual pattern:

### 1. Licensing Information

```yaml
headers:
  license: "This data is provided under MIT License. See https://opensource.org/license/mit for details."
  attribution: "Data provided by YourOrganization. Please include attribution when using."
```

### 2. Data Retention and Caching

```yaml
headers:
  data_retention: "Data provided may be retained for up to 1 day."
  cache_policy: "Results may be cached for up to 2 hours."
```

### 3. UI Components and Rendering

```yaml
headers:
  ui_component: "https://yoursite.com/components/recipe-card.js"
  display_format: "Use card layout with images on left, text on right"
  supported_interactions: "favorite, share, print"
```

### 4. Usage Terms and Restrictions

```yaml
headers:
  usage_terms: "For non-commercial use only. Contact sales@example.com for commercial licensing."
  rate_limits: "100 requests per hour per API key"
  data_freshness: "Data updated daily at 2 AM UTC"
```

### 5. Custom Metadata

```yaml
headers:
  data_source: "Community contributed recipes verified by professional chefs"
  quality_rating: "All items have been tested and rated 4+ stars"
  api_version: "2.0"
```

## Complete Example Configuration

```yaml
# config_nlweb.yaml
headers:
  license: "This data is provided under MIT License. See https://opensource.org/license/mit for details."
  data_retention: "Data provided may be retained for up to 1 day."
  ui_component: "This field may be used to provide a link to the web components that can be used to display the results."
```

This example from the actual implementation shows:
- **license**: Specifies the MIT License with a link to full terms
- **data_retention**: Clear policy on how long data may be cached (1 day)
- **ui_component**: Placeholder for specifying web components for rendering

## Header Format

Based on the PR #205 implementation:

### Message-Based Headers

Headers are sent as individual messages, not HTTP headers:
- Each header key becomes a `message_type` in the response
- Header values are sent as message content
- Headers appear at the beginning of the response stream
- Simple key names without prefixes (e.g., `license`, not `X-License`)

### Example Message Format

In streaming mode, headers appear as:
```json
{"message_type": "license", "content": "This data is provided under MIT License..."}
{"message_type": "data_retention", "content": "Data provided may be retained for up to 1 day."}
{"message_type": "ui_component", "content": "https://example.com/components/..."}
```

In non-streaming mode, they appear at the top level of the response.

## Implementation Details

Headers are sent as individual messages at the beginning of each response session:
- Sent immediately after the API version message
- Each header becomes a separate message with `message_type` matching the header key
- Headers are sent only once per query session
- In non-streaming mode, headers appear at the top level of the JSON response
- In streaming mode, headers are sent as the first messages in the stream

Message flow order:
1. API version message
2. Headers (each as a separate message)
3. "asking_sites" message (if applicable)
4. Results and other content

## Client Integration

Clients should:
1. Process initial messages to extract headers
2. Respect licensing and usage restrictions
3. Implement data retention policies
4. Use UI component links if provided
5. Handle headers gracefully before processing results

## Best Practices

1. **Consistency**: Use consistent header names across your deployment
2. **Documentation**: Document all custom headers for API consumers
3. **Versioning**: Include version information when format changes
4. **Standards**: Follow HTTP header naming conventions
5. **Security**: Don't expose sensitive information in headers
6. **Size**: Keep header values concise to avoid HTTP header size limits

## Common Patterns

### Multi-Instance Deployments

Different instances can have different headers:

```yaml
# recipes.example.com
headers:
  instance_type: "Recipe collection from professional chefs"
  license: "Content licensed under CC-BY-SA-4.0. See https://creativecommons.org/licenses/by-sa/4.0/"
  ui_component: "https://recipes.example.com/components/recipe-card.js"

# movies.example.com  
headers:
  instance_type: "Movie database with ratings and reviews"
  license: "Proprietary content. For licensing inquiries: sales@example.com"
  usage_terms: "For personal use only. Commercial use requires separate license."
```

### Development vs Production

Use environment-specific headers:

```yaml
# Development
headers:
  environment: "Development server - data may be incomplete"
  data_retention: "Test data only - do not retain"
  api_stability: "Unstable - endpoints may change without notice"

# Production
headers:
  environment: "Production"
  data_retention: "Data may be retained for up to 30 days"
  api_stability: "Stable API v2.0"
```

## Future Enhancements

- Dynamic headers based on request context
- Per-endpoint header customization
- Header templates with variable substitution
- Integration with standard protocols (CORS, CSP)
- Automated header validation