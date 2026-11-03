from pathlib import Path
from collections import Counter
import re,json,hashlib
m=json.loads(Path('blind-map.json').read_text())
s=re.sub(r'\s+',' ',Path('hoyle.txt').read_text()).strip()
assert set(m)=={'schemaVersion','corpus','baseline','extent','entries'}
assert m['baseline']['contentHash']==hashlib.sha256(Path('hoyle.txt').read_bytes()).hexdigest()
entries=m['entries']; ids={e['id'] for e in entries}
assert len(ids)==len(entries)
errors=[]; pages=set(); intervals=[]
for e in entries:
    q=re.sub(r'\s+',' ',e['evidence']).strip()
    cite=int(re.search(r'p\. (\d+)$',e['locator']['citation']).group(1))
    spans=[]
    for match in re.finditer(re.escape(q),s):
        pos=match.start(); page=int(re.findall(r'\{(\d+)\}',s[:pos])[-1])
        if page==cite: spans.append((pos,match.end()))
    if len(spans)!=1: errors.append((e['id'],'quote/page resolution',len(spans)))
    else:
        a,b=spans[0]; intervals.append((a,b))
        pages.add(cite)
        pages.update(map(int,re.findall(r'\{(\d+)\}',s[a:b])))
        if e['scope']=='in' and any(not 427<=int(p)<=446 for p in re.findall(r'\{(\d+)\}',s[a:b])):errors.append((e['id'],'quote crosses extent'))
    if e['scope']=='in' and not 427<=cite<=446: errors.append((e['id'],'outside extent'))
    for field in ('dependsOn','enabledBy','suspendedBy'):
        for target in e.get(field,[]):
            if target not in ids or target==e['id']:errors.append((e['id'],field,target))
    if set(e.get('enabledBy',[]))&set(e.get('suspendedBy',[])):errors.append((e['id'],'opposite gates'))
    for ref in e.get('crossReferences',[]):
        if ref['cites'] not in q:errors.append((e['id'],'reference anchor',ref['cites']))
        if ('resolvedBy' in ref)==('unmapped' in ref):errors.append((e['id'],'reference shape'))
        if 'resolvedBy' in ref and ref['resolvedBy'] not in ids:errors.append((e['id'],'reference target'))
    for d in e.get('defines',[]):
        if d['term'] not in q:errors.append((e['id'],'definition anchor',d['term']))
    if e['kind']=='assertion':
        for party in e['assertedBy']:
            if party.casefold() not in q.casefold():errors.append((e['id'],'party anchor',party))
    elif 'assertedBy' in e:errors.append((e['id'],'nonassertion attribution'))
    if e['clarity']=='ambiguous':
        if e.get('ambiguity',{}).get('fate')!='unresolved':errors.append((e['id'],'fate'))
        # Require a substantive three-word verbatim anchor anywhere in map evidence.
        question=e['ambiguity']['question']
        for quoted in re.findall(r'"([^"]+)"',question):
            if quoted not in s:errors.append((e['id'],'nonverbatim quotation in question',quoted))
        all_evidence=' '.join(x['evidence'] for x in entries)
        words=question.split()
        if not any(' '.join(words[i:i+3]).strip('"?.,;:') in all_evidence for i in range(len(words)-2)):
            errors.append((e['id'],'question anchor'))
    elif 'ambiguity' in e:errors.append((e['id'],'clear ambiguity'))
    if 'draws' in e:
        if e['kind']!='operation' or e['scope']!='in':errors.append((e['id'],'draw kind/scope'))
        if e['draws']['dice'].casefold() not in q.casefold():errors.append((e['id'],'draw anchor'))
# Detect dependency cycles.
byid={e['id']:e for e in entries}
def visit(id,path):
    if id in path:raise AssertionError('dependency cycle: '+' -> '.join(path+[id]))
    for dep in byid[id].get('dependsOn',[]):visit(dep,path+[id])
for id in ids:visit(id,[])
if set(range(427,447))-pages:errors.append(('coverage',sorted(set(range(427,447))-pages)))
assert not errors, errors
print('VALID:',len(entries),'entries; all evidence contiguous and on the cited page; all 20 extent pages reached.')
print('Scope:',dict(Counter(e['scope'] for e in entries)))
print('Kinds:',dict(Counter(e['kind'] for e in entries)))
print('Ambiguities:',sum(e['clarity']=='ambiguous' for e in entries))
print('Pointers:',sum(len(e.get('crossReferences',[])) for e in entries))
print('Out-of-extent citations:',[(e['id'],e['locator']['citation']) for e in entries if int(re.search(r'p\. (\d+)$',e['locator']['citation']).group(1))>446])
# Identify unquoted prose for the final coverage review, without dumping whole source pages.
a=s.index('{427}');b=s.index('{447}',a)
covered=[False]*(b-a)
for x,y in intervals:
    for i in range(max(a,x)-a,min(b,y)-a):covered[i]=True
uncovered=[]
runs=[];k=0
while k<b-a:
    if covered[k]: k+=1;continue
    j=k+1
    while j<b-a and not covered[j]:j+=1
    segment=s[a+k:a+j].strip()
    if segment:runs.append((int(re.findall(r'\{(\d+)\}',s[:a+k])[-1]),segment))
    k=j
print('Unquoted runs for review:')
for page,segment in runs:print(page,segment)
