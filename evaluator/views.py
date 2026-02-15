"""
Views: user input form and evaluation results.
"""
import logging
from django.shortcuts import render
from django.views import View
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib import messages

from .scraper import fetch_listings, get_search_url
from .ranking import rank_vehicles_with_llm

logger = logging.getLogger(__name__)

# Set to True to skip scoring/ranking and only show scraped data for verification
SKIP_SCORING_AND_RANKING = False

MAX_VEHICLES_TO_SCORE = 20


class IndexView(View):
    """User input page: only URL-based filters (make, model, location, year range, price range)."""

    def get(self, request):
        try:
            return render(request, 'evaluator/index.html', {
                'form_defaults': {
                    'make': request.GET.get('make', ''),
                    'model': request.GET.get('model', ''),
                    'location': request.GET.get('location', ''),
                    'min_price': request.GET.get('min_price', ''),
                    'max_price': request.GET.get('max_price', ''),
                    'min_year': request.GET.get('min_year', ''),
                    'max_year': request.GET.get('max_year', ''),
                },
            })
        except Exception as e:
            logger.exception('Error rendering index page: %s', e)
            # Return 500 error page if even basic rendering fails
            raise

    def post(self, request):
        try:
            return self._process_post(request)
        except Exception as e:
            # Catch any errors that escape the inner handlers
            logger.exception('Unexpected error in post handler: %s', e)
            messages.error(request, f'Unexpected error: {str(e)}')
            try:
                return render(request, 'evaluator/index.html', {
                    'form_defaults': {
                        'make': request.POST.get('make', ''),
                        'model': request.POST.get('model', ''),
                        'location': request.POST.get('location', ''),
                        'min_price': request.POST.get('min_price', ''),
                        'max_price': request.POST.get('max_price', ''),
                        'min_year': request.POST.get('min_year', ''),
                        'max_year': request.POST.get('max_year', ''),
                    },
                })
            except Exception as render_error:
                logger.exception('Failed to render error page: %s', render_error)
                raise

    def _process_post(self, request):
        def _int(val):
            val = (val or '').strip().replace(',', '')
            try:
                return int(val) if val else None
            except ValueError:
                return None

        make = (request.POST.get('make') or '').strip() or None
        model = (request.POST.get('model') or '').strip() or None
        location = (request.POST.get('location') or '').strip() or None
        min_price = _int(request.POST.get('min_price'))
        max_price = _int(request.POST.get('max_price'))
        min_year = _int(request.POST.get('min_year'))
        max_year = _int(request.POST.get('max_year'))

        # Validate input ranges
        if min_price is not None and max_price is not None and min_price > max_price:
            messages.error(request, 'Error: Minimum price cannot be greater than maximum price')
            try:
                return render(request, 'evaluator/index.html', {
                    'form_defaults': {
                        'make': request.POST.get('make', ''),
                        'model': request.POST.get('model', ''),
                        'location': request.POST.get('location', ''),
                        'min_price': request.POST.get('min_price', ''),
                        'max_price': request.POST.get('max_price', ''),
                        'min_year': request.POST.get('min_year', ''),
                        'max_year': request.POST.get('max_year', ''),
                    },
                })
            except Exception as render_error:
                logger.exception('Failed to render validation error page: %s', render_error)
                raise

        if min_year is not None and max_year is not None and min_year > max_year:
            messages.error(request, 'Error: Minimum year cannot be greater than maximum year')
            try:
                return render(request, 'evaluator/index.html', {
                    'form_defaults': {
                        'make': request.POST.get('make', ''),
                        'model': request.POST.get('model', ''),
                        'location': request.POST.get('location', ''),
                        'min_price': request.POST.get('min_price', ''),
                        'max_price': request.POST.get('max_price', ''),
                        'min_year': request.POST.get('min_year', ''),
                        'max_year': request.POST.get('max_year', ''),
                    },
                })
            except Exception as render_error:
                logger.exception('Failed to render validation error page: %s', render_error)
                raise

        try:
            # Scraper: only URL filters (make, model, location, year range, price range)
            listings = fetch_listings(
                make=make,
                model=model,
                location=location,
                min_year=min_year,
                max_year=max_year,
                min_price=min_price,
                max_price=max_price,
                max_pages=3,
            )
        except Exception as e:
            messages.error(request, f'Error fetching vehicles: {str(e)}')
            logger.exception('Fetch error: %s', e)
            try:
                return render(request, 'evaluator/index.html', {
                    'form_defaults': {
                        'make': request.POST.get('make', ''),
                        'model': request.POST.get('model', ''),
                        'location': request.POST.get('location', ''),
                        'min_price': request.POST.get('min_price', ''),
                        'max_price': request.POST.get('max_price', ''),
                        'min_year': request.POST.get('min_year', ''),
                        'max_year': request.POST.get('max_year', ''),
                    },
                })
            except Exception as render_error:
                logger.exception('Failed to render error page: %s', render_error)
                raise

        if not listings:
            messages.warning(request, 'No vehicles found matching your filters. Try relaxing criteria.')
            try:
                return render(request, 'evaluator/index.html', {
                    'form_defaults': {
                        'make': request.POST.get('make', ''),
                        'model': request.POST.get('model', ''),
                        'location': request.POST.get('location', ''),
                        'min_price': request.POST.get('min_price', ''),
                        'max_price': request.POST.get('max_price', ''),
                        'min_year': request.POST.get('min_year', ''),
                        'max_year': request.POST.get('max_year', ''),
                    },
                })
            except Exception as render_error:
                logger.exception('Failed to render no results page: %s', render_error)
                raise

        # Temporary: skip scoring/ranking and show raw scraped data for verification
        if SKIP_SCORING_AND_RANKING:
            try:
                return render(request, 'evaluator/scraped_preview.html', {
                    'listings': listings,
                    'filters': {
                        'make': make,
                        'model': model,
                        'location': location,
                        'min_price': min_price,
                        'max_price': max_price,
                        'min_year': min_year,
                        'max_year': max_year,
                    },
                    'search_url': get_search_url(make, model, location, min_year, max_year, min_price, max_price),
                })
            except Exception as render_error:
                logger.exception('Failed to render preview page: %s', render_error)
                messages.error(request, f'Error displaying preview: {str(render_error)}')
                return render(request, 'evaluator/index.html', {
                    'form_defaults': {
                        'make': request.POST.get('make', ''),
                        'model': request.POST.get('model', ''),
                        'location': request.POST.get('location', ''),
                        'min_price': request.POST.get('min_price', ''),
                        'max_price': request.POST.get('max_price', ''),
                        'min_year': request.POST.get('min_year', ''),
                        'max_year': request.POST.get('max_year', ''),
                    },
                })

        # Limit how many we send to LLM for ranking
        to_rank = listings[:MAX_VEHICLES_TO_SCORE]
        
        try:
            # Use LLM to rank vehicles and get top 10
            top_10_vehicles = rank_vehicles_with_llm(to_rank)
        except Exception as e:
            messages.error(request, f'Error ranking vehicles: {str(e)}')
            logger.exception('Ranking error: %s', e)
            try:
                return render(request, 'evaluator/index.html', {
                    'form_defaults': {
                        'make': request.POST.get('make', ''),
                        'model': request.POST.get('model', ''),
                        'location': request.POST.get('location', ''),
                        'min_price': request.POST.get('min_price', ''),
                        'max_price': request.POST.get('max_price', ''),
                        'min_year': request.POST.get('min_year', ''),
                        'max_year': request.POST.get('max_year', ''),
                    },
                })
            except Exception as render_error:
                logger.exception('Failed to render ranking error page: %s', render_error)
                raise
        
        # Format for display (just wrap vehicles in dict structure)
        try:
            top_10 = [{'vehicle': vehicle} for vehicle in top_10_vehicles if vehicle]
        except Exception as e:
            logger.exception('Error formatting vehicles: %s', e)
            messages.error(request, f'Error formatting results: {str(e)}')
            return render(request, 'evaluator/index.html', {
                'form_defaults': {
                    'make': request.POST.get('make', ''),
                    'model': request.POST.get('model', ''),
                    'location': request.POST.get('location', ''),
                    'min_price': request.POST.get('min_price', ''),
                    'max_price': request.POST.get('max_price', ''),
                    'min_year': request.POST.get('min_year', ''),
                    'max_year': request.POST.get('max_year', ''),
                },
            })

        # Store in session for optional re-filter view (we keep same results, re-filter is just new search)
        try:
            request.session['last_result'] = {
                'top_10': top_10,
                'filters': {
                    'make': make,
                    'model': model,
                    'location': location,
                    'min_price': min_price,
                    'max_price': max_price,
                    'min_year': min_year,
                    'max_year': max_year,
                },
                'search_url': get_search_url(make, model, location, min_year, max_year, min_price, max_price),
            }
        except Exception as e:
            logger.warning('Failed to store results in session: %s', e)
            # Continue anyway - session storage is a nice-to-have feature

        try:
            search_url = get_search_url(make, model, location, min_year, max_year, min_price, max_price)
        except Exception as e:
            logger.warning('Error building search URL for results: %s', e)
            search_url = None

        try:
            return render(request, 'evaluator/results.html', {
                'top_10': top_10,
                'filters': {
                    'make': make,
                    'model': model,
                    'location': location,
                    'min_price': min_price,
                    'max_price': max_price,
                    'min_year': min_year,
                    'max_year': max_year,
                },
                'search_url': search_url,
            })
        except Exception as e:
            logger.exception('Error rendering results page: %s', e)
            messages.error(request, f'Error displaying results: {str(e)}')
            return render(request, 'evaluator/index.html', {
                'form_defaults': {
                    'make': request.POST.get('make', ''),
                    'model': request.POST.get('model', ''),
                    'location': request.POST.get('location', ''),
                    'min_price': request.POST.get('min_price', ''),
                    'max_price': request.POST.get('max_price', ''),
                    'min_year': request.POST.get('min_year', ''),
                    'max_year': request.POST.get('max_year', ''),
                },
            })


def results_view(request):
    """Display results from session (e.g. after redirect) or show empty state."""
    try:
        data = request.session.get('last_result')
        if not data:
            messages.info(request, 'No previous results found. Please run a new search.')
            return HttpResponseRedirect(reverse('evaluator:index'))
        
        filters = data.get('filters', {})
        try:
            return render(request, 'evaluator/results.html', {
                'top_10': data.get('top_10', []),
                'filters': filters,
                'search_url': data.get('search_url') or get_search_url(
                    filters.get('make'), filters.get('model'), filters.get('location'),
                    filters.get('min_year'), filters.get('max_year'),
                    filters.get('min_price'), filters.get('max_price'),
                ),
            })
        except Exception as render_error:
            logger.exception('Error rendering results: %s', render_error)
            messages.error(request, f'Error displaying results: {str(render_error)}')
            return HttpResponseRedirect(reverse('evaluator:index'))
    except Exception as e:
        logger.exception('Unexpected error in results view: %s', e)
        messages.error(request, f'Unexpected error: {str(e)}')
        return HttpResponseRedirect(reverse('evaluator:index'))
