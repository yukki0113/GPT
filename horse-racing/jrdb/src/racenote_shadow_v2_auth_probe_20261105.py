import os,json,subprocess
print(json.dumps({"github_token_present":bool(os.environ.get("GITHUB_TOKEN")),"gh_token_present":bool(os.environ.get("GH_TOKEN")),"github_repository":os.environ.get("GITHUB_REPOSITORY"),"github_ref":os.environ.get("GITHUB_REF"),"github_actor":os.environ.get("GITHUB_ACTOR")},ensure_ascii=False))
