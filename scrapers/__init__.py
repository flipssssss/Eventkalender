"""Event scrapers package.

Each scraper turns a website into a list of :class:`Event` objects.
The aggregator (``aggregate.py``) collects events from all scrapers,
removes duplicates, sorts them by date and writes the result to
``docs/data/events.json`` for the web feed.
"""
