"""Plant #44 LEDGER-AT-IMPORT: venue scripts must print their routes from ROUTES.md
before their first venue call. Call ledger(*keys) at script top; a route not printed
before use counts as invented."""
import os, re
_ROUTES = os.environ.get("ORGANS_ROUTES") or os.path.join(os.path.dirname(__file__), '..', 'ROUTES.md')  # suite shim: ORGANS_ROUTES names the map explicitly; deployed default is the map beside the rigs' parent
def ledger(*keys):
    path=os.path.abspath(_ROUTES)
    text=open(path,encoding='utf-8',errors='ignore').read()
    lines=[l for l in text.splitlines() if any(re.search(k,l,re.I) for k in keys)]
    print('ROUTES-LEDGER (grep of ROUTES.md for %s):' % list(keys))
    for l in lines[:12]: print('  ', l.strip()[:160])
    if not lines: print('   NO LEDGER LINE - any route used from here is INVENTED; resolve at venue surface first.')
    return lines
