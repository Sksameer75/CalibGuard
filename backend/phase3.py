"""Phase 3: reproducible, labelled anomalies and independent integrity checks.

Run after Phase 2D generation:
    python -m backend.phase3 --input data/generated --output data/phase3 --seed 20261022
"""
from __future__ import annotations
import argparse
import copy
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

FMT = '%Y-%m-%d %H:%M:%S'
PK = {'instrument_types':'instrument_type_id','suppliers':'supplier_id','assets':'asset_id',
      'calibration_plans':'plan_id','calibration_events':'calibration_id','certificates':'certificate_id',
      'work_orders':'work_order_id','work_order_assets':None,'impact_assessments':'assessment_id',
      'emergency_extensions':'extension_id','alerts':'alert_id','audit_records':'audit_id',
      'lifecycle_events':'lifecycle_event_id','production_uses':'use_id'}
FK = [('assets','instrument_type_id','instrument_types','instrument_type_id'),
      ('assets','supplier_id','suppliers','supplier_id'),('calibration_plans','asset_id','assets','asset_id'),
      ('calibration_events','asset_id','assets','asset_id'),('calibration_events','plan_id','calibration_plans','plan_id'),
      ('calibration_events','supplier_id','suppliers','supplier_id'),
      ('certificates','calibration_id','calibration_events','calibration_id'),('certificates','asset_id','assets','asset_id'),
      ('work_orders','calibration_id','calibration_events','calibration_id'),
      ('work_order_assets','work_order_id','work_orders','work_order_id'),('work_order_assets','asset_id','assets','asset_id'),
      ('impact_assessments','calibration_id','calibration_events','calibration_id'),
      ('emergency_extensions','asset_id','assets','asset_id'),('alerts','asset_id','assets','asset_id'),
      ('alerts','calibration_id','calibration_events','calibration_id'),('alerts','use_id','production_uses','use_id'),
      ('production_uses','asset_id','assets','asset_id')]
KINDS = ('INCORRECT_RECORDED_DUE_DATE','EXPIRED_USE_WITHOUT_EXCEPTION',
         'CERTIFICATE_ASSET_MISMATCH','FAILED_CALIBRATION_MISSING_IMPACT')

def load(folder: Path):
    tables={}
    for name in PK:
        file=folder / f'{name}.csv'
        if file.exists():
            with file.open(newline='',encoding='utf-8') as f:
                tables[name]=list(csv.DictReader(f))
    required=set(PK)
    if set(tables)!=required:
        raise ValueError(f'Missing input CSVs: {sorted(required-set(tables))}')
    return tables

def as_dt(value):
    return datetime.strptime(value,FMT)

def inject(original: dict, seed: int=20261022, per_type: int=3):
    """Mutate only copies; labels are never inserted into business tables."""
    if per_type<1: raise ValueError('per_type must be >=1')
    data=copy.deepcopy(original)
    labels=[]
    def mark(kind,table,key,record,field,description):
        labels.append(dict(anomaly_id=f'ANOM-{len(labels)+1:05d}',anomaly_type=kind,
                           table_name=table,record_id=record[key],field_name=field,
                           expected_rule=description))
    events=data['calibration_events']
    passing=[r for r in events if r['result']=='PASS' and r['recorded_due_at'] and r['recorded_due_at']==r['calculated_due_at']]
    passing.sort(key=lambda r:r['calibration_id'])
    if len(passing)<per_type: raise ValueError('Not enough passing calibrations')
    for r in passing[:per_type]:
        r['recorded_due_at']=(as_dt(r['recorded_due_at'])+timedelta(days=11)).strftime(FMT)
        mark(KINDS[0],'calibration_events','calibration_id',r,'recorded_due_at','recorded_due_at must equal calculated_due_at for PASS')

    event_by_asset=defaultdict(list)
    for r in events: event_by_asset[r['asset_id']].append(r)
    for rows in event_by_asset.values(): rows.sort(key=lambda r:(r['performed_at'],r['calibration_id']))
    extensions=defaultdict(list)
    for r in data['emergency_extensions']:
        if r['approval_state']=='APPROVED': extensions[r['asset_id']].append(r)
    # Pick currently nonexecuted BLOCK uses where the latest passing calibration has expired,
    # and there is no approved extension. A failed latest calibration also disqualifies the asset.
    candidates=[]
    for use in data['production_uses']:
        if use['decision']!='BLOCK' or str(use['was_executed']) not in ('0','False','false'): continue
        when=use['used_at']; aid=use['asset_id']
        history=[e for e in event_by_asset[aid] if e['performed_at']<=when]
        if not history: continue
        last=history[-1]
        if last['result']!='PASS' or not last['calculated_due_at'] or last['calculated_due_at']>=when: continue
        if any(e['approved_from']<=when<=e['approved_until'] for e in extensions[aid]): continue
        candidates.append(use)
    candidates.sort(key=lambda r:r['use_id'])
    if len(candidates)<per_type: raise ValueError('Not enough expired, nonexecuted blocked uses')
    for r in candidates[:per_type]:
        r['was_executed']='1'
        mark(KINDS[1],'production_uses','use_id',r,'was_executed',
             'Overdue production use executed with BLOCK decision and no approved extension')

    assets={r['asset_id'] for r in data['assets']}
    certs=sorted(data['certificates'],key=lambda r:r['certificate_id'])
    if len(certs)<per_type or len(assets)<2: raise ValueError('Not enough certificates/assets')
    event_by_id={r['calibration_id']:r for r in events}
    for r in certs[:per_type]:
        actual=event_by_id[r['calibration_id']]['asset_id']
        r['asset_id']=next(a for a in sorted(assets) if a!=actual)
        mark(KINDS[2],'certificates','certificate_id',r,'asset_id',
             'certificate.asset_id must equal calibration_event.asset_id')

    assessed={r['calibration_id'] for r in data['impact_assessments']}
    failed=sorted((r for r in events if r['result']=='FAIL' and r['calibration_id'] in assessed),
                  key=lambda r:r['calibration_id'])
    if len(failed)<per_type: raise ValueError('Not enough failed calibrations with assessments')
    chosen={r['calibration_id'] for r in failed[:per_type]}
    data['impact_assessments']=[r for r in data['impact_assessments'] if r['calibration_id'] not in chosen]
    for r in failed[:per_type]:
        mark(KINDS[3],'calibration_events','calibration_id',r,'impact_assessment',
             'FAIL calibration must have an impact assessment')
    return data,labels

def detect(data):
    findings=[]
    def add(kind,table,record_id,field):
        findings.append((kind,table,record_id,field))
    events={r['calibration_id']:r for r in data['calibration_events']}
    for r in events.values():
        if r['result']=='PASS' and r['recorded_due_at']!=r['calculated_due_at']:
            add(KINDS[0],'calibration_events',r['calibration_id'],'recorded_due_at')
    for r in data['certificates']:
        e=events.get(r['calibration_id'])
        if e and r['asset_id']!=e['asset_id']:
            add(KINDS[2],'certificates',r['certificate_id'],'asset_id')
    assessed={r['calibration_id'] for r in data['impact_assessments']}
    for r in events.values():
        if r['result']=='FAIL' and r['calibration_id'] not in assessed:
            add(KINDS[3],'calibration_events',r['calibration_id'],'impact_assessment')
    by_asset=defaultdict(list)
    for e in events.values():by_asset[e['asset_id']].append(e)
    for v in by_asset.values():v.sort(key=lambda e:(e['performed_at'],e['calibration_id']))
    exts=defaultdict(list)
    for e in data['emergency_extensions']:
        if e['approval_state']=='APPROVED':exts[e['asset_id']].append(e)
    for u in data['production_uses']:
        if str(u['was_executed']) not in ('1','True','true') or u['decision']!='BLOCK':continue
        history=[e for e in by_asset[u['asset_id']] if e['performed_at']<=u['used_at']]
        if not history:continue
        last=history[-1]
        if last['result']!='PASS' or not last['calculated_due_at'] or last['calculated_due_at']>=u['used_at']:continue
        if any(x['approved_from']<=u['used_at']<=x['approved_until'] for x in exts[u['asset_id']]):continue
        add(KINDS[1],'production_uses',u['use_id'],'was_executed')
    return findings

def validate_integrity(data):
    errors=[]
    for table,pk in PK.items():
        rows=data[table]
        if pk:
            values=[r[pk] for r in rows]
            if len(values)!=len(set(values)) or any(not x for x in values): errors.append(f'{table}: duplicate/empty PK')
    bridge=[(r['work_order_id'],r['asset_id']) for r in data['work_order_assets']]
    if len(bridge)!=len(set(bridge)): errors.append('work_order_assets: duplicate composite PK')
    for src,col,target,tcol in FK:
        values={r[tcol] for r in data[target]}
        missing=sum(bool(r[col]) and r[col] not in values for r in data[src])
        if missing:errors.append(f'{src}.{col}: {missing} invalid FK references')
    plans={p['plan_id']:p for p in data['calibration_plans']}
    for e in data['calibration_events']:
        if plans[e['plan_id']]['asset_id']!=e['asset_id']:
            errors.append(f'{e["calibration_id"]}: plan/asset mismatch')
    return errors

def write_csv(path,rows,columns):
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=columns,lineterminator='\n')
        writer.writeheader();writer.writerows(rows)

def run(input_dir:Path,output_dir:Path,seed:int,per_type:int):
    base=load(input_dir)
    baseline_findings=detect(base)
    changed,labels=inject(base,seed,per_type)
    output_dir.mkdir(parents=True,exist_ok=True)
    for name,rows in changed.items():
        write_csv(output_dir/f'{name}.csv',rows,list(base[name][0]))
    label_columns=['anomaly_id','anomaly_type','table_name','record_id','field_name','expected_rule']
    write_csv(output_dir/'ground_truth.csv',labels,label_columns)
    (output_dir/'ground_truth.json').write_text(json.dumps(labels,indent=2)+'\n',encoding='utf-8')
    detected=set(detect(changed)); baseline=set(baseline_findings)
    new_findings=detected-baseline
    expected={(r['anomaly_type'],r['table_name'],r['record_id'],r['field_name']) for r in labels}
    errors=validate_integrity(changed)
    counts=Counter(r['anomaly_type'] for r in labels)
    report={'seed':seed,'injected_anomalies':len(labels),'anomaly_counts':dict(sorted(counts.items())),
            'baseline_findings':len(baseline),'total_findings':len(detected),
            'new_findings':len(new_findings),'labelled_findings_detected':len(expected & detected),
            'unmatched_labels':len(expected-detected),'unexpected_new_findings':len(new_findings-expected),
            'integrity_errors':errors,'pass':not errors and expected<=detected and not(new_findings-expected)}
    (output_dir/'validation_report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    manifest={'seed':seed,'synthetic':True,'stage':'phase3_labelled_anomalies','files':{}}
    for path in sorted(output_dir.iterdir()):
        if path.is_file() and path.name!='manifest.json':
            manifest['files'][path.name]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    (output_dir/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2,sort_keys=True))
    if not report['pass']:raise SystemExit(1)
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=Path('data/generated'))
    parser.add_argument('--output',type=Path,default=Path('data/phase3'))
    parser.add_argument('--seed',type=int,default=20261022)
    parser.add_argument('--per-type',type=int,default=3)
    args=parser.parse_args()
    if args.input.resolve()==args.output.resolve():parser.error('Input and output must differ')
    run(args.input,args.output,args.seed,args.per_type)
if __name__=='__main__':main()
