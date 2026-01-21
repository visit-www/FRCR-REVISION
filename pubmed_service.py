"""
PubMed Integration Service for FRCR-Revision

Purpose: Provide residents with current classifications, criteria, and guideline updates
directly inside the app. Focuses on free full-text articles from preferred radiology journals.

Exam Relevance: Supports FRCR 2B candidates by providing:
- Current BI-RADS, LI-RADS, WHO classifications
- Latest guidelines and management criteria
- Case reviews from Radiographics, AJR, Indian Journal of Radiology
- Free full-text access where available
"""

import os
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json
import hashlib

try:
    from Bio import Entrez
    BIOPYTHON_AVAILABLE = True
except ImportError:
    BIOPYTHON_AVAILABLE = False
    print("Warning: Bio.Entrez not available. Install biopython for better PubMed integration.")


# Preferred radiology journals for FRCR exam preparation
PREFERRED_JOURNALS = [
    "Radiographics",
    "American Journal of Roentgenology",
    "AJR",
    "Indian Journal of Radiology and Imaging",
    "Clinical Radiology",
    "British Journal of Radiology",
    "European Radiology",
    "Radiology",
    "Journal of Medical Imaging and Radiation Sciences"
]

# Cache configuration
CACHE_DIR = os.path.join(os.path.dirname(__file__), 'cache', 'pubmed')
CACHE_DURATION_HOURS = 24  # Cache results for 24 hours


def ensure_cache_dir():
    """Create cache directory if it doesn't exist."""
    os.makedirs(CACHE_DIR, exist_ok=True)


def get_cache_key(query: str, filters: Dict) -> str:
    """Generate cache key from query and filters."""
    cache_data = f"{query}_{json.dumps(filters, sort_keys=True)}"
    return hashlib.md5(cache_data.encode()).hexdigest()


def get_cached_result(cache_key: str) -> Optional[List[Dict]]:
    """Retrieve cached result if still valid."""
    ensure_cache_dir()
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    
    if not os.path.exists(cache_file):
        return None
    
    try:
        with open(cache_file, 'r') as f:
            cached_data = json.load(f)
        
        # Check if cache is still valid
        cache_time = datetime.fromisoformat(cached_data.get('timestamp', ''))
        if datetime.now() - cache_time < timedelta(hours=CACHE_DURATION_HOURS):
            return cached_data.get('results')
    except Exception as e:
        print(f"Cache read error: {e}")
    
    return None


def cache_result(cache_key: str, results: List[Dict]):
    """Cache search results."""
    ensure_cache_dir()
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    
    try:
        with open(cache_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'results': results
            }, f)
    except Exception as e:
        print(f"Cache write error: {e}")


def build_pubmed_query(topic: str, filters: Optional[Dict] = None) -> str:
    """
    Build PubMed query string with exam-relevant filters.
    SIMPLIFIED: Less restrictive query that actually returns results.
    
    Args:
        topic: Search topic (e.g., "BI-RADS", "lung cancer staging")
        filters: Optional filters (free_full_text, article_type, date_range)
    
    Returns:
        Formatted PubMed query string
    """
    filters = filters or {}
    
    # Simplified query: topic + radiology context (no mandatory journal filter)
    # This is much less restrictive and will return results
    query = f"{topic} AND radiology"
    
    # Only add free full text filter if explicitly requested
    # Otherwise, we search all and prioritize free ones in results
    if filters.get('free_full_text_only', False):
        query += " AND free full text[filter]"
    
    # Article type filters (optional)
    article_types = filters.get('article_type', [])
    if article_types:
        types = " OR ".join([f'"{t}"[Publication Type]' for t in article_types])
        query += f" AND ({types})"
    
    # Date range filter (optional)
    if filters.get('date_range'):
        date_range = filters['date_range']
        if isinstance(date_range, dict):
            if 'from' in date_range:
                query += f" AND {date_range['from']}:{date_range.get('to', '3000')}[Publication Date]"
    
    return query


def search_pubmed(topic: str, max_results: int = 20, filters: Optional[Dict] = None) -> List[Dict]:
    """
    Search PubMed for articles related to a topic.
    
    Exam Relevance: Helps candidates find current guidelines and case reviews
    for FRCR exam preparation.
    
    Args:
        topic: Search topic (e.g., diagnosis, classification system)
        max_results: Maximum number of results to return
        filters: Optional filters (free_full_text, article_type, date_range)
    
    Returns:
        List of article dictionaries with title, authors, journal, year, abstract, PMID, full-text links
    """
    filters = filters or {}
    
    # Check cache first
    cache_key = get_cache_key(topic, filters)
    cached = get_cached_result(cache_key)
    if cached:
        return cached[:max_results]
    
    # Build query
    query = build_pubmed_query(topic, filters)
    print(f"[DEBUG] PubMed query: {query}")
    
    results = []
    
    if BIOPYTHON_AVAILABLE:
        # Use Bio.Entrez (preferred method)
        try:
            # Set email (required by NCBI)
            Entrez.email = os.getenv('PUBMED_EMAIL', 'frcr-revision@example.com')
            
            # Search PubMed
            handle = Entrez.esearch(
                db="pubmed",
                term=query,
                retmax=max_results,
                sort="relevance",
                retmode="xml"
            )
            search_results = Entrez.read(handle)
            handle.close()
            
            pmids = search_results['IdList']
            print(f"[DEBUG] PubMed found {len(pmids)} results")
            
            if not pmids:
                # Try simpler query as fallback
                print(f"[DEBUG] No results, trying simpler query: {topic} radiology")
                simple_query = f"{topic} radiology"
                handle = Entrez.esearch(
                    db="pubmed",
                    term=simple_query,
                    retmax=max_results,
                    sort="relevance",
                    retmode="xml"
                )
                search_results = Entrez.read(handle)
                handle.close()
                pmids = search_results['IdList']
                print(f"[DEBUG] Fallback query found {len(pmids)} results")
                
                if not pmids:
                    return []
            
            # Fetch article details
            handle = Entrez.efetch(
                db="pubmed",
                id=",".join(pmids),
                retmode="xml"
            )
            articles = Entrez.read(handle)
            handle.close()
            
            # Parse articles
            for article in articles['PubmedArticle']:
                try:
                    medline = article['MedlineCitation']
                    pmid = str(medline['PMID'])
                    
                    # Get article data
                    article_data = medline.get('Article', {})
                    title = article_data.get('ArticleTitle', 'No title')
                    
                    # Authors
                    author_list = article_data.get('AuthorList', [])
                    authors = []
                    for author in author_list[:5]:  # Limit to first 5 authors
                        last_name = author.get('LastName', '')
                        first_name = author.get('ForeName', '')
                        if last_name:
                            authors.append(f"{last_name} {first_name}".strip())
                    
                    # Journal
                    journal = article_data.get('Journal', {})
                    journal_title = journal.get('Title', 'Unknown Journal')
                    journal_iso = journal.get('ISOAbbreviation', journal_title)
                    
                    # Publication date
                    pub_date = article_data.get('Journal', {}).get('JournalIssue', {}).get('PubDate', {})
                    year = pub_date.get('Year', '')
                    if not year and 'MedlineDate' in pub_date:
                        year = pub_date['MedlineDate'][:4] if pub_date['MedlineDate'] else ''
                    
                    # Abstract
                    abstract_parts = article_data.get('Abstract', {}).get('AbstractText', [])
                    if isinstance(abstract_parts, list):
                        abstract = ' '.join([str(part) for part in abstract_parts])
                    else:
                        abstract = str(abstract_parts) if abstract_parts else ''
                    
                    # Check for free full text (PMC)
                    pmc_id = None
                    full_text_link = None
                    for article_id in article_data.get('ELocationID', []):
                        if article_id.attributes.get('EIdType') == 'pmc':
                            pmc_id = str(article_id)
                            # Remove "PMC" prefix if already present
                            pmc_id_clean = pmc_id.replace('PMC', '').replace('pmc', '').strip()
                            full_text_link = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id_clean}/"
                            break
                    
                    # If no PMC, check PubmedCentral
                    if not pmc_id:
                        for id_list in article.get('PubmedData', {}).get('ArticleIdList', []):
                            if id_list.attributes.get('IdType') == 'pmc':
                                pmc_id = str(id_list)
                                # Remove "PMC" prefix if already present
                                pmc_id_clean = pmc_id.replace('PMC', '').replace('pmc', '').strip()
                                full_text_link = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id_clean}/"
                                break
                    
                    # PubMed link
                    pubmed_link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                    
                    # DOI
                    doi = None
                    for id_list in article.get('PubmedData', {}).get('ArticleIdList', []):
                        if id_list.attributes.get('IdType') == 'doi':
                            doi = str(id_list)
                            break
                    
                    article_dict = {
                        'pmid': pmid,
                        'title': title,
                        'authors': authors,
                        'journal': journal_title,
                        'journal_iso': journal_iso,
                        'year': year,
                        'abstract': abstract[:500] + '...' if len(abstract) > 500 else abstract,
                        'pubmed_link': pubmed_link,
                        'full_text_link': full_text_link,
                        'doi': doi,
                        'has_free_full_text': full_text_link is not None
                    }
                    
                    # Prioritize free full-text articles (add to beginning)
                    if full_text_link:
                        results.insert(0, article_dict)
                    else:
                        results.append(article_dict)
                    
                except Exception as e:
                    print(f"Error parsing article: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            # Rate limiting (NCBI requires delays)
            time.sleep(0.34)  # ~3 requests per second
            
        except Exception as e:
            print(f"Bio.Entrez error: {e}")
            # Fallback to requests-based method
            results = _search_pubmed_requests(query, max_results)
    else:
        # Fallback to requests-based method
        results = _search_pubmed_requests(query, max_results)
    
    # Cache results
    if results:
        cache_result(cache_key, results)
    
    return results[:max_results]


def _search_pubmed_requests(query: str, max_results: int) -> List[Dict]:
    """
    Fallback PubMed search using requests (when Bio.Entrez not available).
    Less feature-rich but works without biopython.
    FIXED: Prioritizes free full-text articles.
    """
    free_text_articles = []
    other_articles = []
    
    try:
        print(f"[DEBUG] Using requests fallback for query: {query}")
        # Search using E-utilities
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            'db': 'pubmed',
            'term': query,
            'retmax': max_results * 2,  # Get more to filter
            'retmode': 'json',
            'sort': 'relevance'
        }
        
        response = requests.get(search_url, params=params, timeout=10)
        print(f"[DEBUG] PubMed search response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            pmids = data.get('esearchresult', {}).get('idlist', [])
            print(f"[DEBUG] PubMed found {len(pmids)} PMIDs")
            
            if not pmids:
                # Try even simpler query
                simple_query = query.split(' AND ')[0] + ' radiology'
                print(f"[DEBUG] Trying simpler query: {simple_query}")
                params['term'] = simple_query
                response = requests.get(search_url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    pmids = data.get('esearchresult', {}).get('idlist', [])
                    print(f"[DEBUG] Simpler query found {len(pmids)} PMIDs")
            
            if pmids:
                # Fetch summaries
                fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                fetch_params = {
                    'db': 'pubmed',
                    'id': ','.join(pmids),
                    'retmode': 'json'
                }
                
                fetch_response = requests.get(fetch_url, params=fetch_params, timeout=10)
                if fetch_response.status_code == 200:
                    summaries = fetch_response.json().get('result', {})
                    
                    for pmid in pmids:
                        if pmid in summaries:
                            summary = summaries[pmid]
                            
                            # Check for PMC (free full text)
                            article_ids = summary.get('articleids', [])
                            pmc_id = None
                            full_text_link = None
                            for aid in article_ids:
                                if aid.get('idtype') == 'pmc':
                                    pmc_id = aid.get('value', '')
                                    if pmc_id:
                                        # Remove "PMC" prefix if already present
                                        pmc_id_clean = str(pmc_id).replace('PMC', '').replace('pmc', '').strip()
                                        full_text_link = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id_clean}/"
                                    break
                            
                            article_dict = {
                                'pmid': pmid,
                                'title': summary.get('title', 'No title'),
                                'authors': summary.get('authors', []),
                                'journal': summary.get('source', 'Unknown Journal'),
                                'journal_iso': summary.get('source', ''),
                                'year': summary.get('pubdate', '').split(' ')[0] if summary.get('pubdate') else '',
                                'abstract': '',  # Not available in summary
                                'pubmed_link': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                                'full_text_link': full_text_link,
                                'doi': None,
                                'has_free_full_text': full_text_link is not None
                            }
                            
                            # Prioritize free full-text
                            if full_text_link:
                                free_text_articles.append(article_dict)
                            else:
                                other_articles.append(article_dict)
        
        # Rate limiting
        time.sleep(0.34)
        
    except Exception as e:
        print(f"Requests-based PubMed search error: {e}")
        import traceback
        traceback.print_exc()
    
    # Combine: free full-text first
    return free_text_articles + other_articles


def search_latest_guidelines(topic: str, max_results: int = 10) -> List[Dict]:
    """
    Search for latest guidelines and reviews on a topic.
    
    Exam Relevance: Helps candidates find current classification systems and
    management guidelines for FRCR exam preparation.
    
    Args:
        topic: Topic to search (e.g., "BI-RADS", "LI-RADS")
        max_results: Maximum number of results
    
    Returns:
        List of guideline/review articles
    """
    filters = {
        'free_full_text': True,
        'article_type': ['Guideline', 'Practice Guideline', 'Review', 'Systematic Review'],
        'date_range': {'from': '2020'}  # Last 4 years
    }
    
    return search_pubmed(topic, max_results=max_results, filters=filters)
