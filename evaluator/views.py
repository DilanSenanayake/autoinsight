"""
Views: user input form and evaluation results.
"""
from django.shortcuts import render
from django.views import View
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib import messages

from .scraper import fetch_listings, get_search_url
from .ranking import rank_vehicles_with_llm

# Set to True to skip scoring/ranking and only show scraped data for verification
SKIP_SCORING_AND_RANKING = False

MAX_VEHICLES_TO_SCORE = 20


class IndexView(View):
    """User input page: only URL-based filters (make, model, location, year range, price range)."""

    def get(self, request):
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

    def post(self, request):
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
        if not listings:
            messages.warning(request, 'No vehicles found matching your filters. Try relaxing criteria.')
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

        # Temporary: skip scoring/ranking and show raw scraped data for verification
        if SKIP_SCORING_AND_RANKING:
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

        # Limit how many we send to LLM for ranking
        to_rank = listings[:MAX_VEHICLES_TO_SCORE]
        
        # Use LLM to rank vehicles and get top 10
        top_10_vehicles = rank_vehicles_with_llm(to_rank)
        
        # Format for display (just wrap vehicles in dict structure)
        top_10 = [{'vehicle': vehicle} for vehicle in top_10_vehicles]

        # Store in session for optional re-filter view (we keep same results, re-filter is just new search)
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
            'search_url': get_search_url(make, model, location, min_year, max_year, min_price, max_price),
        })


def results_view(request):
    """Display results from session (e.g. after redirect) or show empty state."""
    data = request.session.get('last_result')
    if not data:
        return HttpResponseRedirect(reverse('evaluator:index'))
    filters = data.get('filters', {})
    return render(request, 'evaluator/results.html', {
        'top_10': data['top_10'],
        'filters': filters,
        'search_url': data.get('search_url') or get_search_url(
            filters.get('make'), filters.get('model'), filters.get('location'),
            filters.get('min_year'), filters.get('max_year'),
            filters.get('min_price'), filters.get('max_price'),
        ),
    })
