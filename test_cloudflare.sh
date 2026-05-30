#!/bin/bash
echo "Logging in..."
# We need valid credentials. I'll just use a fake one, but it will return 401.
# Let's see if we can get valid credentials from the DB or just test the 401 response differences.
# Actually, I can use the API directly to check if the Cookie header reaches the app!
