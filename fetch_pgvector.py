import urllib.request, json

url = "https://api.github.com/repos/portalcorp/pgvector_compiled/releases"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())

for rel in data[:5]:
    tag = rel.get("tag_name", "")
    name = rel.get("name", "")
    print(f"Release: {tag} - {name}")
    for asset in rel.get("assets", []):
        aname = asset["name"]
        if "win" in aname.lower() or "16" in aname:
            print(f"  -> {aname} : {asset['browser_download_url']}")
    print()
