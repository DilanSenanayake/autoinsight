"""
WSGI config for Vehicle Evaluator project.
"""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vehicle_evaluator.settings')

application = get_wsgi_application()
