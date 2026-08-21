import json,sys,os,collections
T=sys.argv[1]
recs=[json.loads(l) for l in open(T,encoding='utf-8',errors='replace') if l.strip().startswith('{')]
turn=0; ev=[]
for r in recs:
    t=r.get('type')
    if t=='user': turn+=1
    if t=='assistant':
        m=r.get('message') or {}
        for b in (m.get('content') or []):
            if isinstance(b,dict) and b.get('type')=='tool_use':
                p=(b.get('input') or {}).get('file_path','')
                if b.get('name') in ('Edit','Write','NotebookEdit') and p:
                    ev.append((turn,'EDIT',os.path.basename(p)))
    if t=='attachment':
        a=r.get('attachment') or {}
        if a.get('type')=='edited_text_file':
            ev.append((turn,'FLUSH',os.path.basename(a.get('filename','?'))))

files=set(f for _,k,f in ev if k=='FLUSH')
print("For each file that ever appeared in a flush:\n")
print("  %-26s %-28s %-22s %s" % ("file","Edit/Write turns","flush turns","last flush AFTER last Edit?"))
for f in sorted(files, key=lambda x:-sum(1 for _,k,g in ev if k=='FLUSH' and g==x)):
    edits=[t for t,k,g in ev if k=='EDIT' and g==f]
    flush=[t for t,k,g in ev if k=='FLUSH' and g==f]
    after = (max(flush) > max(edits)) if edits else None
    print("  %-26s %-28s %-22s %s"
          % (f, (str(edits[-4:]) if edits else "NEVER"),
             str(flush[-4:]), "YES" if after else ("no" if after is False else "n/a (never edited)")))

print("\n--- test: does an Edit stop subsequent flushes of that file? ---")
for f in sorted(files):
    edits=[t for t,k,g in ev if k=='EDIT' and g==f]
    flush=[t for t,k,g in ev if k=='FLUSH' and g==f]
    if not edits: continue
    after=[t for t in flush if t>max(edits)]
    print("  %-26s last Edit turn %-5s  flushes after it: %s"
          % (f, max(edits), after if after else "NONE  <-- cleared"))
