"""
URL configuration for Vehicle Evaluator project.
"""
from django.urls import path, include

urlpatterns = [
    path('', include('evaluator.urls')),
]
