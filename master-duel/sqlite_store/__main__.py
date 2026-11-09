"""Read one JSON request from stdin; return one JSON response."""
import json
import sys
from . import Store

OPERATIONS = {'initialize','version','add_card','get_card','update_card','search_cards','resolve_name','get_inventory','set_inventory','batch_diff','history','undo_batch','integrity_check','set_attributes','get_attributes','set_md_catalog','get_md_catalog'}

def main():
    store = None
    try:
        request = json.load(sys.stdin)
        if set(request) - {'db','operation','args'} or request['operation'] not in OPERATIONS: raise ValueError('invalid request')
        if request['operation'] == 'initialize':
            if request.get('args', {}): raise ValueError('initialize takes no args')
            store = Store.create(request['db'])
            result = None
        else:
            store = Store(request['db'])
            result = getattr(store, request['operation'])(**request.get('args', {}))
        print(json.dumps({'ok':True,'result':result},ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({'ok':False,'error':str(exc)},ensure_ascii=False))
        return 1
    finally:
        if store: store.close()
    return 0

if __name__ == '__main__': sys.exit(main())
