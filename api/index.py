# Vercel serverless entry: expose Django WSGI app.
# The @ardnt/vercel-python-wsgi builder looks for a WSGI callable named "app".
from vehicle_evaluator.wsgi import application

app = application
