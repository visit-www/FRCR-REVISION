# AJCC Website API Exploration Report

## Summary
Explored the AJCC Staging Online website (https://ajccstaging.org) to determine if TNM and staging data can be accessed programmatically.

## Key Findings

### 1. **API Endpoints Discovered**
The AJCC website uses a RESTful JSON API that is accessible without authentication for basic structure, but content requires login:

#### Structure API
- **URL Pattern**: `https://ajccstaging.org/api/structure/{section}?locale=en`
- **Example**: `https://ajccstaging.org/api/structure/thorax?locale=en`
- **Purpose**: Returns navigation structure and hierarchy
- **Authentication**: Not required (public)

#### Content API
- **URL Pattern**: `https://ajccstaging.org/api/content/{path}?locale=en&add-headers=true`
- **Example**: `https://ajccstaging.org/api/content/thorax/lung?locale=en&add-headers=true`
- **Purpose**: Returns detailed content for a specific disease site
- **Authentication**: Required for full content (returns empty content without login)

### 2. **API Response Structure**
The content API returns JSON with the following structure:

```json
{
  "content": "...",           // HTML content (empty without auth)
  "title": "Lung",
  "href": "thorax/lung",
  "chunked_sections": [],    // Sectioned content
  "headers": [],              // Table of contents headers
  "children": [],             // Sub-pages
  "breadcrumbs": [],          // Navigation path
  "previous": {...},          // Previous page
  "next": {...},              // Next page
  "parent": {...},            // Parent section
  "versions": [],             // Available diagnosis years (2024, 2025, 2026)
  "metadata": {},
  "relatedLinks": []
}
```

### 3. **Authentication Method**
- **Provider**: Okta OAuth2
- **Login URL**: `https://login.facs.org/oauth2/v1/authorize`
- **Flow**: OAuth2 authorization code flow
- **Credentials**: Username/password stored in environment variables (`AJCC_USERNAME`, `AJCC_PASSWORD`)

### 4. **Data Format**
- **Format**: JSON (RESTful API)
- **Content Type**: `application/json; charset=utf-8`
- **Content**: HTML content within JSON (requires parsing)
- **Structure**: Hierarchical with sections, versions, and metadata

## Recommendations for Implementation

### Option 1: **Web Scraping with Authentication** (Recommended)
1. **Login Flow**:
   - Use OAuth2 flow to authenticate with Okta
   - Maintain session cookies
   - Access protected API endpoints

2. **Data Extraction**:
   - Fetch content from `/api/content/{section}/{disease}/{year}` endpoints
   - Parse HTML content to extract TNM staging tables
   - Use BeautifulSoup or similar to extract structured data

3. **Implementation Steps**:
   ```python
   # Pseudo-code
   1. Authenticate via Okta OAuth2
   2. Store session cookies
   3. Fetch: /api/content/{section}/{disease}/{year}
   4. Parse HTML content for TNM tables
   5. Extract T, N, M stages and stage groupings
   6. Store in structured format (JSON/database)
   ```

### Option 2: **Direct API Integration**
- Use the discovered API endpoints directly
- Requires maintaining authenticated session
- Parse HTML content from JSON responses
- Extract TNM data from HTML tables

### Option 3: **Cached/Pre-fetched Data**
- Periodically fetch and cache TNM data
- Store in local database
- Update when new versions are released

## Implementation Considerations

### Authentication Challenges
1. **OAuth2 Flow**: Requires handling redirects and state management
2. **Session Management**: Cookies need to be maintained
3. **Token Refresh**: May need to handle token expiration

### Data Extraction Challenges
1. **HTML Parsing**: Content is HTML within JSON, requires parsing
2. **Table Extraction**: TNM data is in HTML tables, need robust extraction
3. **Version Management**: Multiple diagnosis years (2024-2026) need handling
4. **Structure Changes**: Website structure may change over time

### Legal/Technical Considerations
1. **Terms of Service**: Check AJCC terms regarding automated access
2. **Rate Limiting**: Implement rate limiting to avoid blocking
3. **Error Handling**: Robust error handling for network/auth failures
4. **Caching**: Cache data to minimize API calls

## Next Steps

1. **Test Authentication**:
   - Implement OAuth2 login flow
   - Verify access to protected endpoints
   - Test session persistence

2. **Extract Sample Data**:
   - Fetch one disease site (e.g., Lung) with authentication
   - Parse HTML content
   - Extract TNM staging tables
   - Validate data structure

3. **Build Extraction Service**:
   - Create `ajcc_tnm_extractor.py` module
   - Implement HTML parsing for TNM tables
   - Structure data as JSON/database records

4. **Integration**:
   - Integrate with existing `ajcc_service.py`
   - Add admin route for TNM retrieval
   - Cache extracted data

## API Endpoint Examples

### Structure Endpoint
```
GET https://ajccstaging.org/api/structure/thorax?locale=en
```

### Content Endpoint (Public - Limited)
```
GET https://ajccstaging.org/api/content/thorax/lung?locale=en&add-headers=true
```

### Content Endpoint (Authenticated - Full)
```
GET https://ajccstaging.org/api/content/thorax/lung/2026?locale=en&add-headers=true
Authorization: [OAuth2 token or session cookies]
```

## Conclusion

✅ **Yes, it is possible to get TNM and staging data programmatically!**

The AJCC website provides a JSON API that can be accessed after authentication. The data is in HTML format within JSON responses, which can be parsed to extract TNM staging information. Implementation will require:

1. OAuth2 authentication handling
2. HTML content parsing
3. Table extraction for TNM data
4. Structured data storage

The recommended approach is to build a service that authenticates, fetches content, and extracts TNM data into a structured format for use in the application.
