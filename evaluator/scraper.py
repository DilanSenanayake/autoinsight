"""
Riyasewana scraper: fetch and filter vehicle listings.
URL pattern: /search/cars/{make}/{model}/{location}/{min_year}-{max_year}/price-{min_price}-{max_price}
"""
import datetime
import time
import re
import logging
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = 'https://riyasewana.com'
SEARCH_CARS = f'{BASE_URL}/search/cars'
# Browser-like headers; cookies from homepage visit are sent with requests
REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': BASE_URL + '/',
}
# cloudscraper bypasses Cloudflare/bot protection (fixes 403)
try:
    import cloudscraper
    SESSION = cloudscraper.create_scraper()
except ImportError:
    SESSION = requests.Session()
SESSION.headers.update(REQUEST_HEADERS)


def _slug(s) -> str:
    """Normalize segment for URL: lowercase, strip, replace spaces with hyphen."""
    try:
        if not s or not str(s).strip():
            return None
        return str(s).strip().lower().replace(' ', '-')
    except Exception as e:
        logger.warning('Error slugifying %s: %s', s, e)
        return None


def _make_search_url(
    make=None,
    model=None,
    location=None,
    min_year=None,
    max_year=None,
    min_price=None,
    max_price=None,
    page=1,
):
    """
    Build Riyasewana search URL. Only non-null filters are added.
    When no filters: use /search (same as site pagination). With filters: /search/cars/make/model/location/year/price.
    """
    try:
        has_filters = any((
            make,
            model,
            location,
            (min_year is not None and min_year > 0),
            (max_year is not None and max_year > 0),
            (min_price is not None and min_price >= 0),
            (max_price is not None and max_price > 0),
        ))
        if not has_filters:
            # Riyasewana pagination uses /search?page=N (see sample response)
            url = urljoin(BASE_URL, '/search')
            if page > 1:
                url += f'?page={page}'
            return url
        path = '/search/cars'
        make_s = _slug(make)
        if make_s:
            path += '/' + make_s
        model_s = _slug(model)
        if model_s:
            path += '/' + model_s
        location_s = _slug(location)
        if location_s:
            path += '/' + location_s
        if min_year is not None and min_year > 0 or max_year is not None and max_year > 0:
            year_min = int(min_year) if min_year is not None and min_year > 0 else 2000
            year_max = int(max_year) if max_year is not None and max_year > 0 else datetime.date.today().year
            path += f'/{year_min}-{year_max}'
        if min_price is not None and min_price >= 0 or max_price is not None and max_price > 0:
            price_min = int(min_price) if min_price is not None and min_price >= 0 else 0
            price_max = int(max_price) if max_price is not None and max_price > 0 else 50_000_000
            path += f'/price-{price_min}-{price_max}'
        url = urljoin(BASE_URL, path.strip('/'))
        if page > 1:
            url += f'?page={page}'
        return url
    except Exception as e:
        logger.exception('Error building search URL with filters make=%s, model=%s, location=%s: %s', make, model, location, e)
        raise RuntimeError(f'Failed to build search URL: {str(e)}') from e


def get_search_url(make=None, model=None, location=None, min_year=None, max_year=None, min_price=None, max_price=None):
    """Build the Riyasewana search URL for the given filters (page 1). For display/link on results."""
    try:
        url = _make_search_url(
            make=make, model=model, location=location,
            min_year=min_year, max_year=max_year,
            min_price=min_price, max_price=max_price,
            page=1,
        )
        logger.debug('Built display search URL: %s', url)
        return url
    except Exception as e:
        logger.warning('Error building display search URL: %s', e)
        # Return base search URL as fallback
        return f'{BASE_URL}/search'


def _extract_cards(soup):
    """
    Extract vehicle listing cards from Riyasewana search results.
    Structure (from sample): <ul> with <li class="item round"> per listing.
    """
    try:
        # Riyasewana uses li.item for each listing (inside #content ul)
        cards = soup.select('li.item')
        return cards
    except Exception as e:
        logger.warning('Error extracting cards from soup: %s', e)
        return []


def _extract_link_from_card(card, base_url=BASE_URL):
    """
    Stage 1 only: extract detail URL and optional name from a listing card.
    Returns dict with url, name (or None if no link).
    """
    try:
        link = card.select_one('h2.more a') or card.select_one('.imgbox a') or card.find('a', href=re.compile(r'/buy/'))
        if not link or not link.get('href'):
            return None
        url = urljoin(base_url, link['href']) if not link['href'].startswith('http') else link['href']
        name = (link.get('title') or link.get_text(strip=True) or '')[:200]
        return {'url': url, 'name': name}
    except Exception as e:
        logger.warning('Error extracting link from card: %s', e)
        return None


def _stage2_fetch_detail_page(url):
    """Stage 2 only: GET vehicle detail URL, return BeautifulSoup or None."""
    if not url or not str(url).strip():
        return None
    url = str(url).strip()
    try:
        resp = SESSION.get(url, timeout=15, cookies=SESSION.cookies)
        logger.debug('Detail page response - status: %d, size: %d bytes', resp.status_code, len(resp.text))
        resp.raise_for_status()
        return BeautifulSoup(resp.text, 'html.parser')
    except requests.Timeout as e:
        logger.warning('Timeout fetching detail page: %s', url)
        return None
    except requests.HTTPError as e:
        logger.warning('HTTP %d error fetching detail page: %s', e.response.status_code, url)
        return None
    except requests.RequestException as e:
        logger.warning('Request error fetching detail page %s: %s', url, e)
        return None
    except Exception as e:
        logger.warning('Unexpected error parsing detail page %s: %s', url, e)
        return None


def _stage2_parse_detail(soup, url):
    """
    Stage 2 only: parse one vehicle detail page into a single vehicle dict.
    Structure from sample response2: #content h1 (title), table.moret rows with p.moreh (label) + next td (value).
    """
    vehicle = {
        'url': url,
        'name': '',
        'price': None,
        'mileage': None,
        'year': None,
        'description': '',
        'raw_text': '',
        'make': '',
        'model': '',
        'gear': '',
        'fuel_type': '',
        'options': '',
        'engine_cc': '',
        'details': '',
        'contact': '',
    }
    if not soup:
        logger.debug('No soup provided for URL: %s', url)
        return vehicle
    
    try:
        # Title from h1
        h1 = soup.find('h1')
        if h1:
            vehicle['name'] = (h1.get_text(strip=True) or '')[:200]
    except Exception as e:
        logger.debug('Error parsing title from %s: %s', url, e)

    # Table: each p.moreh is a label, next sibling td is the value
    try:
        table = soup.find('table', class_='moret')
        if not table:
            logger.debug('No detail table found for %s', url)
            return vehicle
        
        for p in table.find_all('p', class_='moreh'):
            try:
                label = (p.get_text() or '').strip()
                parent_td = p.find_parent('td')
                if not parent_td:
                    continue
                next_td = parent_td.find_next_sibling('td')
                if not next_td:
                    continue
                value = (next_td.get_text(separator=' ', strip=True) or '').strip()
                if not label:
                    continue
                if label == 'Contact':
                    vehicle['contact'] = value
                elif label == 'Price':
                    if value and re.search(r'[\d,]+', value):
                        try:
                            vehicle['price'] = int(re.sub(r'[^\d]', '', value))
                        except ValueError:
                            logger.debug('Could not parse price: %s', value)
                elif label == 'Make':
                    vehicle['make'] = value
                elif label == 'Model':
                    vehicle['model'] = value
                elif label == 'YOM':
                    if value:
                        m = re.search(r'(\d{4})', value)
                        if m:
                            try:
                                vehicle['year'] = int(m.group(1))
                            except ValueError:
                                logger.debug('Could not parse year: %s', value)
                elif label == 'Mileage (km)':
                    if value and value != '-' and re.search(r'\d+', value):
                        try:
                            vehicle['mileage'] = int(re.sub(r'[^\d]', '', value))
                        except ValueError:
                            logger.debug('Could not parse mileage: %s', value)
                elif label == 'Gear':
                    vehicle['gear'] = value
                elif label == 'Fuel Type':
                    vehicle['fuel_type'] = value
                elif label == 'Options':
                    vehicle['options'] = value[:500] if value else ''
                elif label == 'Engine (cc)':
                    vehicle['engine_cc'] = value.strip() if value else ''
                elif label == 'Details':
                    vehicle['details'] = value[:3000] if value else ''
            except Exception as e:
                logger.debug('Error parsing field from %s: %s', url, e)
                continue
        
        vehicle['description'] = (vehicle.get('details') or '')[:1500]
        parts = [vehicle['name'], vehicle.get('make'), vehicle.get('model'), vehicle.get('contact')]
        if vehicle.get('price'):
            parts.append('Rs. {}'.format(vehicle['price']))
        if vehicle.get('mileage'):
            parts.append('{} km'.format(vehicle['mileage']))
        vehicle['raw_text'] = ' '.join(str(p) for p in parts if p)
    except Exception as e:
        logger.warning('Error parsing vehicle details from %s: %s', url, e)
    
    return vehicle


def _stage2_collect_vehicles(vehicle_links, limit=2):
    """
    Stage 2: for each of the first `limit` entries in vehicle_links, fetch the detail page
    and parse it into a vehicle dict. Returns list of vehicle dicts.
    """
    if not vehicle_links:
        return []
    
    results = []
    errors = []
    
    for i, entry in enumerate(vehicle_links):
        if i >= limit:
            break
        url = entry.get('url') or ''
        name_fallback = entry.get('name') or ''
        if not url:
            logger.debug('Skipping entry %d: no URL', i)
            continue
        
        try:
            soup = _stage2_fetch_detail_page(url)
            vehicle = _stage2_parse_detail(soup, url)
            if not vehicle.get('name') and name_fallback:
                vehicle['name'] = name_fallback
            results.append(vehicle)
            
            # Add small delay between detail page fetches to avoid rate limiting
            if i < len(vehicle_links) - 1:  # Don't delay after last vehicle
                time.sleep(0.3)  # 0.3 seconds between detail pages
        except Exception as e:
            error_msg = f'Failed to collect vehicle {i} ({name_fallback or url}): {str(e)}'
            logger.warning(error_msg)
            errors.append(error_msg)
            continue
    
    if errors and not results:
        logger.warning('Stage 2 collection errors: %s', '; '.join(errors[:3]))
    
    return results


def fetch_listings(
    make=None,
    model=None,
    location=None,
    min_year=None,
    max_year=None,
    min_price=None,
    max_price=None,
    max_pages=3,
):
    """
    Two-stage fetch:
    Stage 1: Request search page(s), extract vehicle list (detail URLs only).
    Stage 2: Request each vehicle's detail page and collect full vehicle data.

    Returns:
        List of dicts with keys: name, url, price, mileage, year, make, model, gear, fuel_type, options, engine_cc, details, contact, description, raw_text.
    
    Raises:
        Exception: If network request fails or page parsing fails
    """
    MAX_RESULTS = 20
    
    # Log the search filters
    logger.info('Starting vehicle search with filters: make=%s, model=%s, location=%s, year=%s-%s, price=%s-%s, max_pages=%d',
                make or 'any', model or 'any', location or 'any', 
                min_year or '—', max_year or '—',
                min_price or '—', max_price or '—',
                max_pages)
    
    # Visit homepage first to get cookies
    try:
        SESSION.get(BASE_URL, timeout=10, cookies=SESSION.cookies)
        logger.debug('Successfully connected to %s to get cookies', BASE_URL)
    except requests.Timeout:
        raise RuntimeError(f'Timeout while connecting to {BASE_URL}. Website may be slow or unreachable.')
    except requests.ConnectionError:
        raise RuntimeError(f'Cannot connect to {BASE_URL}. Check your internet connection or website may be down.')
    except requests.RequestException as e:
        raise RuntimeError(f'Error reaching {BASE_URL}: {str(e)}')

    # ---------- Stage 1: get vehicle list (links only) – all results up to MAX_RESULTS ----------
    vehicle_links = []
    stage1_errors = []
    
    for page in range(1, max_pages + 1):
        if len(vehicle_links) >= MAX_RESULTS:
            break
        try:
            search_url = _make_search_url(
                make=make,
                model=model,
                location=location,
                min_year=min_year,
                max_year=max_year,
                min_price=min_price,
                max_price=max_price,
                page=page,
            )
            logger.info('Scraping page %d from Riyasewana: %s', page, search_url)
            resp = SESSION.get(search_url, timeout=15, cookies=SESSION.cookies)
            logger.debug('Response status: %d, content length: %d bytes', resp.status_code, len(resp.text))
            resp.raise_for_status()
        except requests.Timeout:
            page_error = f'Timeout on page {page}'
            logger.warning(page_error)
            stage1_errors.append(page_error)
            continue
        except requests.HTTPError as e:
            page_error = f'HTTP {e.response.status_code} on page {page}'
            logger.warning(page_error)
            stage1_errors.append(page_error)
            if e.response.status_code == 403:
                raise RuntimeError(f'Access denied (403) by Riyasewana. Your IP may be blocked or the site blocked the scraper.')
            continue
        except requests.ConnectionError as e:
            page_error = f'Connection error on page {page}'
            logger.warning(page_error)
            stage1_errors.append(page_error)
            continue
        except requests.RequestException as e:
            page_error = f'Request error on page {page}: {str(e)}'
            logger.warning(page_error)
            stage1_errors.append(page_error)
            continue
        
        try:
            soup = BeautifulSoup(resp.text, 'html.parser')
            cards = _extract_cards(soup)
            if not cards:
                # Log HTML sample to debug why no cards found
                page_title = soup.find('title')
                page_title_text = page_title.get_text() if page_title else 'No title'
                html_sample = resp.text[:500] if len(resp.text) > 500 else resp.text
                logger.warning('No cards found on page %d. Page title: %s. HTML sample: %s...', 
                              page, page_title_text, html_sample[:200])
                logger.info('Total vehicle links collected before stopping: %d', len(vehicle_links))
                break
            
            logger.debug('Found %d cards on page %d', len(cards), page)
            links_before = len(vehicle_links)
            
            for card in cards:
                if len(vehicle_links) >= MAX_RESULTS:
                    break
                entry = _extract_link_from_card(card)
                if entry and entry.get('url'):
                    vehicle_links.append(entry)
            
            links_added = len(vehicle_links) - links_before
            logger.info('Page %d: extracted %d valid vehicle links (total so far: %d)', page, links_added, len(vehicle_links))
            
            # Add delay between page requests to avoid rate limiting
            if page < max_pages and len(vehicle_links) < MAX_RESULTS:
                delay = 1  # 1 second between pages
                logger.debug('Waiting %d seconds before next page to avoid rate limiting...', delay)
                time.sleep(delay)
        except Exception as e:
            page_error = f'Error parsing page {page}: {str(e)}'
            logger.exception(page_error)
            stage1_errors.append(page_error)
            continue

    if not vehicle_links:
        # No vehicles found in Stage 1 - this is normal, just return empty
        if stage1_errors:
            logger.warning('Stage 1 failed: No vehicle links found. Errors encountered: %s', 
                          '; '.join(stage1_errors[:3]))
        else:
            logger.warning('Stage 1 complete: No vehicles found matching filters make=%s, model=%s, location=%s, year=%s-%s, price=%s-%s',
                          make or 'any', model or 'any', location or 'any',
                          min_year or '—', max_year or '—',
                          min_price or '—', max_price or '—')
        return []

    # ---------- Stage 2: fetch each vehicle's detail page and collect full data (all stage 1 results) ----------
    logger.info('Stage 1 complete: found %d vehicle links. Starting Stage 2 to fetch details...', len(vehicle_links))
    all_listings = _stage2_collect_vehicles(vehicle_links, limit=MAX_RESULTS)
    
    # Log final summary
    logger.info('Search complete: collected %d vehicles with full details', len(all_listings))
    if all_listings:
        logger.debug('Sample vehicles: %s', ', '.join([v.get('name', 'Unknown') for v in all_listings[:3]]))
    
    # Return what we found, even if it's partial (some links may have failed to fetch details)
    # Empty result is normal and handled gracefully by view
    return all_listings
