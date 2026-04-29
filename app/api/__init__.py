"""Domain API routers extracted from app.main.

Each module in this package owns a slice of the surface that used to live in
the 11k-line main.py monolith. main.py imports the routers and wires them
via `app.include_router`. The middleware (auth_guard) and the lifespan
hooks (`on_startup`, `on_shutdown`) remain in main.py.

Migration is incremental — slices land here when they're stable enough to
move. Keep PR-sized: one router per change, with the corresponding routes
deleted from main.py atomically so we never have two definitions.
"""
