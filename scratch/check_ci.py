import urllib.request
import json
import sys

url = "https://api.github.com/repos/MDaftab76678-1945/Saleha/actions/runs?per_page=5"
req = urllib.request.Request(url, headers={"User-Agent": "SalehaCI-Checker"})

try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        runs = data.get("workflow_runs", [])
        for r in runs:
            print(f"Run ID: {r['id']} | Name: {r['name']} | Status: {r['status']} | Conclusion: {r['conclusion']}")
            print(f"Commit: {r.get('head_sha', '')[:7]} - {r['head_commit']['message'][:60]}")
            
            # Fetch jobs for latest run
            jobs_url = r["jobs_url"]
            j_req = urllib.request.Request(jobs_url, headers={"User-Agent": "SalehaCI-Checker"})
            try:
                with urllib.request.urlopen(j_req) as j_resp:
                    j_data = json.loads(j_resp.read().decode())
                    for job in j_data.get("jobs", []):
                        print(f"  Job: {job['name']} | Status: {job['status']} | Conclusion: {job['conclusion']}")
                        for step in job.get("steps", []):
                            if step.get("conclusion") == "failure":
                                print(f"    FAILED STEP: {step['name']}")
            except Exception as ex:
                print("  Jobs error:", ex)
            print("-" * 50)
except Exception as e:
    print("Error fetching runs:", e)
