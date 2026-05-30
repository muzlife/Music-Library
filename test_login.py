import requests

url = "https://qa-library.muzlife.com/auth/login"
# We don't have the real password, but we can see the Set-Cookie if it succeeds, or maybe it fails with 401 but no Set-Cookie.
# Actually, I can check the exact response headers of the login page.
r = requests.post(url, json={"username": "admin", "password": "wrongpassword"})
print("Login Headers:", r.headers)
