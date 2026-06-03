import requests

url_health = "https://__QA_DOMAIN__/health"
url_ops = "https://__QA_DOMAIN__/ops/placement-hints"

headers = {"Cookie": "__PROJECT_SLUG___session=fake_cookie_value.fake_signature"}

print("GET request:")
r1 = requests.get(url_ops, headers=headers)
print(r1.status_code, r1.text)

print("\nPOST request:")
r2 = requests.post(url_ops, headers=headers)
print(r2.status_code, r2.text)
