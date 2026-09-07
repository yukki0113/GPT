"""Drive request safety validator; API execution needs explicit external setup."""
import argparse,json
OPS={"metadata","list","search","download","verify","upload","mkdir","copy","move","replace","trash"}
def validate_request(r):
    op=r.get("operation")
    if op not in OPS: raise ValueError("unsupported operation")
    if op in {"move","replace","trash"} and not r.get("file_id"): raise ValueError(f"{op} requires file_id")
    if op=="replace" and not r.get("expected",{}).get("file_id"): raise ValueError("replace requires expected.file_id")
    if op=="upload" and r.get("overwrite",False): raise ValueError("upload overwrite is forbidden; use replace with CAS")
    if op in {"upload","mkdir","copy"} and not r.get("parent_folder_id"): raise ValueError("write requires explicit parent_folder_id")
    return r
def main():
    p=argparse.ArgumentParser();p.add_argument("operation");p.add_argument("--request",required=True);a=p.parse_args()
    try:
      r=json.loads(open(a.request,encoding="utf-8").read());r["operation"]=a.operation;print(json.dumps(validate_request(r),ensure_ascii=False));return 0
    except Exception as e: print(json.dumps({"status":"failure","backend":"gdrive","operation":a.operation,"error":str(e)}));return 1
