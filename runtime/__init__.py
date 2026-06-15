"""OpenVINO runtime layer.

Everything that actually touches OpenVINO lives here and is imported lazily, so
the rest of the application (and the web UI) can run on machines without
OpenVINO installed via the built-in mock engine.
"""
