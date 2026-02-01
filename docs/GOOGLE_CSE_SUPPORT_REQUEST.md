# Google Custom Search API – Support Request Template

Copy and paste the below into your Google Cloud Support ticket. Replace `YOUR_API_KEY` with your actual key (or omit if submitting via secure channel).

---

## Summary

We are receiving a 403 error when calling the Custom Search JSON API (cse.list). The error states that the project does not have access to the Custom Search JSON API, despite the API being enabled and billing active.

---

## Project and Credentials

| Item | Value |
|------|-------|
| **Google Cloud Project ID** | `radinsights` |
| **API Key** | `YOUR_API_KEY` *(add your key here or reference: Credentials > API keys in project radinsights)* |
| **Programmable Search Engine ID (cx)** | `d795c77e9ff5346ad` |

---

## Exact API Call

**Method:** `GET`  
**Endpoint:** `https://customsearch.googleapis.com/customsearch/v1`

**Query parameters:**
```
key=YOUR_API_KEY
cx=d795c77e9ff5346ad
q=brain+CT+imaging
searchType=image
num=3
rights=cc_publicdomain,cc_attribute,cc_sharealike
safe=off
```

**Full URL (with key redacted):**
```
GET https://customsearch.googleapis.com/customsearch/v1?key=YOUR_API_KEY&cx=d795c77e9ff5346ad&q=brain%20CT%20imaging&searchType=image&num=3&rights=cc_publicdomain%2Ccc_attribute%2Ccc_sharealike&safe=off
```

**Minimal request (same 403):**
```
GET https://customsearch.googleapis.com/customsearch/v1?key=YOUR_API_KEY&cx=d795c77e9ff5346ad&q=brain%20CT
```

---

## Full Error Response

**HTTP Status:** `200` (response body contains error)

**Response body (JSON):**
```json
{
  "error": {
    "code": 403,
    "message": "This project does not have the access to Custom Search JSON API.",
    "errors": [
      {
        "message": "This project does not have the access to Custom Search JSON API.",
        "domain": "global",
        "reason": "forbidden"
      }
    ]
  }
}
```

---

## Steps Already Taken

- [x] Custom Search JSON API enabled in project `radinsights` (APIs & Services > Enabled APIs)
- [x] Billing enabled and linked to project `radinsights`
- [x] API key has Application restrictions: **None**
- [x] API key has API restrictions: **None** (or restricted to Custom Search JSON API only)
- [x] Using canonical endpoint `https://customsearch.googleapis.com/customsearch/v1`
- [x] Programmable Search Engine (cx) created and configured for “Search the entire web”
- [x] Minimal request (key, cx, q only) also returns the same 403

---

## Question

What additional steps or project configuration are required for project `radinsights` to access the Custom Search JSON API? Is there a known restriction for new projects or specific regions?

---

## Contact

*(Add your email or support contact)*
