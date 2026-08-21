import json,sys,os,collections,hashlib
T=sys.argv[1]
recs=[json.loads(l) for l in open(T,encoding='utf-8',errors='replace') if l.strip().startswith('{')]

turn=0; timeline=[]           # (turn, kind, payload)
for r in recs:
    t=r.get('type')
    if t=='user': turn+=1
    if t=='assistant':
        m=r.get('message') or {}
        for b in (m.get('content') or []):
            if isinstance(b,dict) and b.get('type')=='tool_use':
                timeline.append((turn,'tool',b.get('name'),(b.get('input') or {}).get('file_path','')))
    if t=='attachment':
        a=r.get('attachment') or {}
        if a.get('type')=='edited_text_file':
            sn=a.get('snippet') or ''
            timeline.append((turn,'reinj',os.path.basename(a.get('filename','?')),
                             hashlib.md5(sn.encode()).hexdigest()[:6]+':'+str(len(sn))))

reinj=[x for x in timeline if x[1]=='reinj']
turns_with = collections.Counter(x[0] for x in reinj)
last_turn=max(x[0] for x in timeline)

print("total user turns observed :", last_turn)
print("turns containing a flush  :", len(turns_with), "of", last_turn)
print("re-injection events       :", len(reinj))

print("\n--- flush size per turn (turn: count) ---")
print("  ", dict(sorted(turns_with.items())))

print("\n--- per file: when it entered, when last seen, how many times ---")
per=collections.defaultdict(list)
for t,_,f,h in reinj: per[f].append((t,h))
# last turn each file was actually written by a tool
lastwrite={}
for t,k,name,path in timeline:
    if k=='tool' and name in ('Edit','Write','NotebookEdit') and path:
        lastwrite[os.path.basename(path)]=t
print("  %-26s %5s %6s %6s %8s" % ("file","n","first","last","span"))
for f,v in sorted(per.items(), key=lambda kv:-len(kv[1])):
    ts=[t for t,_ in v]
    print("  %-26s %5d %6d %6d %8d" % (f,len(v),min(ts),max(ts),max(ts)-min(ts)))

print("\n--- does a file ever LEAVE the set? (gaps between consecutive flushes) ---")
allflush=sorted(turns_with)
for f,v in sorted(per.items(), key=lambda kv:-len(kv[1]))[:5]:
    ts=sorted(set(t for t,_ in v))
    inrange=[t for t in allflush if min(ts)<=t<=max(ts)]
    missed=[t for t in inrange if t not in ts]
    print("  %-26s present in %d/%d flushes within its span; absent from %s"
          % (f,len(ts),len(inrange), missed if missed else "none"))

print("\n--- is the payload always identical? ---")
for f,v in sorted(per.items(), key=lambda kv:-len(kv[1]))[:6]:
    hs=collections.Counter(h for _,h in v)
    print("  %-26s %d distinct payload(s): %s" % (f,len(hs),dict(hs)))
