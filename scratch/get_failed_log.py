import urllib.request

job_id = "99616534038"
url = f"https://api.github.com/repos/MDaftab76678-1945/Saleha/actions/jobs/{job_id}/logs"
opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

try:
    with opener.open(req) as resp:
        content = resp.read().decode("utf-8", errors="replace")
        lines = content.splitlines()
        print(f"Total log lines: {len(lines)}")
        for l in lines[-70:]:
            print(l)
except Exception as e:
    print("Error fetching log:", e)
