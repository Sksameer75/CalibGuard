"""CalibGuard Phase 3B: dataset validation, deterministic replay and portable exports.

Run: python -m backend.phase3b --input data/phase3 --output data/phase3b
Run: python -m backend.phase3b --input data/phase3 --output data/phase3b --replay
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .phase3 import PK, FK, KINDS, load, detect, validate_integrity

DATE_FMT = '%Y-%m-%d %H:%M:%S'
DATE_FIELDS = {
 'assets':('commissioned_at','retired_at'),
 'calibration_plans':('effective_from','effective_to'),
 'calibration_events':('performed_at','calculated_due_at','recorded_due_at','recorded_at'),
 'certificates':('issued_at','valid_until'),
 'work_orders':('opened_at','started_at','completed_at'),
 'emergency_extensions':('approved_from','approved_until'),
 'production_uses':('used_at','evaluated_at'),
 'impact_assessments':('created_at','closed_at'),
 'alerts':('created_at',), 'audit_records':('occurred_at',),
 'lifecycle_events':('occurred_at',)
}
ENUMS = {
 ('suppliers','supplier_kind'):{'MANUFACTURER','CALIBRATION_LAB','BOTH'},
 ('assets','lifecycle_state'):{'ACTIVE','QUARANTINED','RETIRED'},
 ('calibration_plans','state'):{'ACTIVE','SUPERSEDED','CANCELLED'},
 ('calibration_events','result'):{'PASS','FAIL'},
 ('certificates','certificate_status'):{'ISSUED','REVOKED'},
 ('work_orders','work_type'):{'SCHEDULED_CALIBRATION','CORRECTIVE_ACTION','INSPECTION'},
 ('work_orders','status'):{'OPEN','IN_PROGRESS','COMPLETED','CANCELLED'},
 ('emergency_extensions','approval_state'):{'REQUESTED','APPROVED','REJECTED','REVOKED'},
 ('production_uses','decision'):{'ALLOW','CONDITIONAL_ALLOW','BLOCK'},
 ('impact_assessments','status'):{'OPEN','IN_PROGRESS','COMPLETED'},
 ('alerts','severity'):{'INFO','WARNING','CRITICAL'},
 ('alerts','alert_state'):{'OPEN','ACKNOWLEDGED','RESOLVED'},
 ('lifecycle_events','entity_name'):{'ASSET','CALIBRATION_PLAN','CERTIFICATE','WORK_ORDER','EMERGENCY_EXTENSION','ALERT','IMPACT_ASSESSMENT'},
}
NUMBERS = {
 'instrument_types':{'tolerance':'decimal','default_interval_days':'positive_int'},
 'calibration_plans':{'interval_days':'positive_int','policy_requires_block':'bool','requires_certificate':'bool'},
 'calibration_events':{'reference_value':'decimal','measured_value':'decimal','absolute_error':'nonnegative_decimal','tolerance_at_test':'positive_decimal'},
 'work_orders':{'downtime_minutes':'nonnegative_int'},
 'production_uses':{'was_executed':'bool'},
}
NULLABLE = {
 'suppliers':{'accreditation_reference'}, 'assets':{'supplier_id','retired_at'},
 'calibration_plans':{'effective_to'},
 'calibration_events':{'supplier_id','calculated_due_at','recorded_due_at'},
 'certificates':{'document_reference'},
 'work_orders':{'calibration_id','started_at','completed_at'},
 'impact_assessments':{'closed_at','notes'},
 'emergency_extensions':{'approver_reference'},
 'alerts':{'calibration_id','use_id'},
 'lifecycle_events':{'from_state','reason'},
}
# Only intentional, labelled anomalies are exempted from these business rules.
LABEL_RULE = {'INCORRECT_RECORDED_DUE_DATE':'DUE_DATE_MISMATCH',
              'CERTIFICATE_ASSET_MISMATCH':'CERTIFICATE_ASSET_MISMATCH',
              'FAILED_CALIBRATION_MISSING_IMPACT':'MISSING_IMPACT',
              'EXPIRED_USE_WITHOUT_EXCEPTION':'EXECUTED_BLOCKED_USE'}
SQL_ORDER = ('instrument_types','suppliers','assets','calibration_plans','calibration_events',
             'certificates','work_orders','work_order_assets','impact_assessments',
             'emergency_extensions','production_uses','alerts','audit_records','lifecycle_events')

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def parse_dt(value): return datetime.strptime(value, DATE_FMT)

def inspect(data, labels):
    errors=[]; warnings=[]; counts=Counter(); samples=[]
    labelled={(LABEL_RULE[x['anomaly_type']],x['table_name'],x['record_id']) for x in labels}
    def issue(rule,table,key,detail,expected=False):
        counts[rule]+=1
        if len(samples)<60: samples.append({'rule':rule,'table':table,'record_id':key,'detail':detail,'labelled':expected})
        if not expected: errors.append(f'{rule} {table}/{key}: {detail}')
    for msg in validate_integrity(data): errors.append('INTEGRITY: '+msg)
    for table, rows in data.items():
        if table not in PK: continue
        key_field=PK[table]
        for index,r in enumerate(rows):
            key=r.get(key_field,'') if key_field else f'row-{index+1}'
            for field,value in r.items():
                if value=='' and field not in NULLABLE.get(table,set()):
                    issue('REQUIRED',table,key,field+' is empty')
                if value and (table,field) in ENUMS and value not in ENUMS[(table,field)]:
                    issue('ENUM',table,key,field+'='+value)
                if value and field in DATE_FIELDS.get(table,()):
                    try: parse_dt(value)
                    except ValueError: issue('DATETIME',table,key,field+'='+value)
                kind=NUMBERS.get(table,{}).get(field)
                if kind and value:
                    try:
                        n=Decimal(value)
                        if not n.is_finite(): raise ValueError('nonfinite')
                        if kind=='bool' and value not in ('0','1'): raise ValueError('not 0/1')
                        if kind.endswith('int') and n!=n.to_integral_value(): raise ValueError('not integer')
                        if kind.startswith('positive') and n<=0: raise ValueError('not positive')
                        if kind.startswith('nonnegative') and n<0: raise ValueError('negative')
                    except (InvalidOperation,ValueError): issue('NUMBER',table,key,field+'='+value)
            if table=='audit_records':
                try: json.loads(r['details'])
                except (ValueError,TypeError): issue('AUDIT_JSON',table,key,'invalid JSON details')
    events={e['calibration_id']:e for e in data['calibration_events']}
    assessments={a['calibration_id'] for a in data['impact_assessments']}
    types={t['instrument_type_id']:t for t in data['instrument_types']}
    plans={p['plan_id']:p for p in data['calibration_plans']}
    assets={a['asset_id']:a for a in data['assets']}
    for e in data['calibration_events']:
        eid=e['calibration_id']
        try:
            error=abs(Decimal(e['measured_value'])-Decimal(e['reference_value']))
            tolerance=Decimal(e['tolerance_at_test'])
            if error!=Decimal(e['absolute_error']): issue('ERROR_ARITHMETIC','calibration_events',eid,'absolute_error mismatch')
            expected='PASS' if error<=tolerance else 'FAIL'
            if e['result']!=expected: issue('PASS_FAIL','calibration_events',eid,'incorrect result')
            if e['result']=='PASS':
                due=parse_dt(e['performed_at'])
                from datetime import timedelta
                due+=timedelta(days=int(plans[e['plan_id']]['interval_days']))
                if e['calculated_due_at']!=due.strftime(DATE_FMT): issue('DUE_CALCULATION','calibration_events',eid,'calculated_due_at mismatch')
                if e['recorded_due_at']!=e['calculated_due_at']:
                    issue('DUE_DATE_MISMATCH','calibration_events',eid,'recorded_due_at mismatch',('DUE_DATE_MISMATCH','calibration_events',eid) in labelled)
            else:
                if e['calculated_due_at'] or e['recorded_due_at']: issue('FAIL_HAS_DUE','calibration_events',eid,'failed calibration has due date')
                if eid not in assessments:
                    issue('MISSING_IMPACT','calibration_events',eid,'failed calibration has no assessment',('MISSING_IMPACT','calibration_events',eid) in labelled)
            if parse_dt(e['recorded_at'])<parse_dt(e['performed_at']): issue('EVENT_ORDER','calibration_events',eid,'recorded before performed')
            if e['asset_id'] in assets and e['plan_id'] in plans and plans[e['plan_id']]['asset_id']!=e['asset_id']:
                issue('PLAN_ASSET','calibration_events',eid,'plan belongs to different asset')
        except (ValueError,KeyError,InvalidOperation,OverflowError) as ex:
            issue('CALIBRATION_PARSE','calibration_events',eid,str(ex))
    for c in data['certificates']:
        cid=c['certificate_id']; e=events.get(c['calibration_id'])
        if e and c['asset_id']!=e['asset_id']:
            issue('CERTIFICATE_ASSET_MISMATCH','certificates',cid,'different existing asset',('CERTIFICATE_ASSET_MISMATCH','certificates',cid) in labelled)
        try:
            if parse_dt(c['valid_until'])<parse_dt(c['issued_at']): issue('CERT_DATES','certificates',cid,'expires before issued')
        except ValueError: pass
    for w in data['work_orders']:
        try:
            opened=parse_dt(w['opened_at']); started=parse_dt(w['started_at']) if w['started_at'] else None
            completed=parse_dt(w['completed_at']) if w['completed_at'] else None
            if started and started<opened or completed and (not started or completed<started): issue('WORK_ORDER_DATES','work_orders',w['work_order_id'],'invalid order')
            if started and completed and int((completed-started).total_seconds()//60)!=int(w['downtime_minutes']): issue('DOWNTIME','work_orders',w['work_order_id'],'duration mismatch')
        except ValueError: pass
    for e in data['emergency_extensions']:
        try:
            if parse_dt(e['approved_until'])<=parse_dt(e['approved_from']): issue('EXTENSION_DATES','emergency_extensions',e['extension_id'],'invalid window')
        except ValueError: pass
    for u in data['production_uses']:
        try:
            if parse_dt(u['evaluated_at'])<parse_dt(u['used_at']): issue('USE_DATES','production_uses',u['use_id'],'evaluated before used')
        except ValueError: pass
    for x in data['lifecycle_events']:
        if x['from_state'] and x['from_state']==x['to_state']:
            issue('LIFECYCLE_NO_CHANGE','lifecycle_events',x['lifecycle_event_id'],'from and to states equal')
    # Business-rule findings for executed blocked uses are expected baseline findings,
    # not structural errors; they are counted and reported separately.
    executed=sum(u['decision']=='BLOCK' and u['was_executed']=='1' for u in data['production_uses'])
    detected={(LABEL_RULE.get(k,k),t,i) for k,t,i,_ in detect(data)}
    missing=[x for x in labelled if x not in detected]
    for kind,table,record_id in missing: issue('UNDETECTED_LABEL',table,record_id,kind)
    return {'pass':not errors,'structural_errors':len(errors),'error_examples':errors[:50],
            'rule_counts':dict(sorted(counts.items())),'samples':samples,
            'labelled_anomalies':len(labels),'labels_detected':len(labels)-len(missing),
            'executed_blocked_uses':executed,
            'warnings':['Executed BLOCK decisions are compliance findings, not structural errors.'],
            'table_counts':{name:len(rows) for name,rows in data.items()}}

def sql_literal(value,kind):
    if value=='': return 'NULL'
    if kind in ('decimal','positive_decimal','nonnegative_decimal','positive_int','nonnegative_int','bool'):
        return value
    return "'"+value.replace('\\','\\\\').replace("'","''").replace('\x00','')+"'"

def write_sql(data, path, batch=500):
    with path.open('w',encoding='utf-8',newline='\n') as f:
        f.write('-- CalibGuard synthetic dataset; import AFTER database/schema.sql\n')
        f.write('SET NAMES utf8mb4;\nSTART TRANSACTION;\n')
        for table in SQL_ORDER:
            rows=data[table]
            if not rows: continue
            columns=list(rows[0]); names=', '.join('`'+c+'`' for c in columns)
            for i in range(0,len(rows),batch):
                f.write(f'INSERT INTO `{table}` ({names}) VALUES\n')
                vals=[]
                for row in rows[i:i+batch]:
                    vals.append('('+', '.join(sql_literal(row[c],NUMBERS.get(table,{}).get(c)) for c in columns)+')')
                f.write(',\n'.join(vals)+';\n')
        f.write('COMMIT;\n')

def write_jsonl(data,path):
    with path.open('w',encoding='utf-8',newline='\n') as f:
        for table in SQL_ORDER:
            for row in data[table]:
                f.write(json.dumps({'table':table,'record':row},sort_keys=True,ensure_ascii=False)+'\n')

def replay(seed, expected_dir):
    """Generate twice independently, including Phase 3 anomaly injection, compare CSV SHA256."""
    with tempfile.TemporaryDirectory(prefix='calibguard-replay-') as tmp:
        root=Path(tmp); outputs=[]
        for n in (1,2):
            generated=root/f'generated{n}'; labelled=root/f'phase3_{n}'
            subprocess.run([sys.executable,'-m','backend.generator','--scale','full','--seed',str(seed),'--output',str(generated)],check=True,stdout=subprocess.DEVNULL)
            subprocess.run([sys.executable,'-m','backend.phase3','--input',str(generated),'--output',str(labelled),'--seed',str(seed)],check=True,stdout=subprocess.DEVNULL)
            outputs.append(labelled)
        names=[f'{table}.csv' for table in SQL_ORDER]+['ground_truth.csv','ground_truth.json']
        mismatch=[]
        for name in names:
            hashes=[sha(d/name) for d in outputs]+[sha(expected_dir/name)]
            if len(set(hashes))!=1: mismatch.append({'file':name,'hashes':hashes})
        return {'pass':not mismatch,'runs':2,'compared_files':len(names),'mismatches':mismatch,
                'seed':seed,'scale':'full'}

def write_dictionary(data,path):
    """Machine-readable field dictionary, using observed columns and declared rules."""
    fkmap={(src,col):f'{target}.{target_col}' for src,col,target,target_col in FK}
    units={('instrument_types','tolerance'):'measurement_unit of instrument type',
           ('calibration_events','reference_value'):'asset instrument type unit',
           ('calibration_events','measured_value'):'asset instrument type unit',
           ('calibration_events','absolute_error'):'asset instrument type unit',
           ('calibration_events','tolerance_at_test'):'asset instrument type unit',
           ('work_orders','downtime_minutes'):'minutes',
           ('calibration_plans','interval_days'):'days',
           ('instrument_types','default_interval_days'):'days'}
    dictionary={}
    for table in SQL_ORDER:
        fields=[]
        for field in data[table][0]:
            kind=NUMBERS.get(table,{}).get(field)
            inferred='DATETIME' if field in DATE_FIELDS.get(table,()) else ('DECIMAL' if kind and 'decimal' in kind else 'INTEGER' if kind and ('int' in kind or kind=='bool') else 'VARCHAR/TEXT')
            if table=='audit_records' and field=='details': inferred='JSON'
            fields.append({'name':field,'logical_type':inferred,
                           'required':field not in NULLABLE.get(table,set()),
                           'primary_key':field==PK[table] if PK[table] else field in ('work_order_id','asset_id'),
                           'foreign_key':fkmap.get((table,field)),
                           'allowed_values':sorted(ENUMS[(table,field)]) if (table,field) in ENUMS else ([0,1] if kind=='bool' else None),
                           'unit':units.get((table,field)),
                           'validation':kind or ('ISO timestamp YYYY-MM-DD HH:MM:SS' if inferred=='DATETIME' else None)})
        dictionary[table]={'fields':fields,'row_count':len(data[table]),
                           'notes':'Logical dictionary: consult database/schema.sql for exact SQL lengths, indexes and constraints.'}
    path.write_text(json.dumps(dictionary,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def run(input_dir,output_dir,seed=20261022,do_replay=False,do_sql=True):
    data=load(input_dir)
    with (input_dir/'ground_truth.csv').open(newline='',encoding='utf-8') as f: labels=list(csv.DictReader(f))
    report=inspect(data,labels)
    output_dir.mkdir(parents=True,exist_ok=True)
    if do_replay:
        report['reproducibility']=replay(seed,input_dir)
        report['pass']=report['pass'] and report['reproducibility']['pass']
    if do_sql: write_sql(data,output_dir/'dataset.sql')
    write_jsonl(data,output_dir/'dataset.jsonl')
    write_dictionary(data,output_dir/'data_dictionary.json')
    report['exports']={'jsonl':'dataset.jsonl','sql':'dataset.sql' if do_sql else None,'data_dictionary':'data_dictionary.json'}
    report['source_manifest_sha256']=sha(input_dir/'manifest.json') if (input_dir/'manifest.json').exists() else None
    (output_dir/'quality_report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    files={p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(output_dir.iterdir()) if p.is_file() and p.name!='export_manifest.json'}
    (output_dir/'export_manifest.json').write_text(json.dumps({'seed':seed,'source':str(input_dir),'files':files},indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('samples','error_examples')},indent=2,sort_keys=True))
    if not report['pass']: raise SystemExit(1)
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=Path('data/phase3'))
    p.add_argument('--output',type=Path,default=Path('data/phase3b'))
    p.add_argument('--seed',type=int,default=20261022)
    p.add_argument('--replay',action='store_true',help='regenerate full dataset twice and compare hashes')
    p.add_argument('--skip-sql',action='store_true')
    a=p.parse_args()
    if a.input.resolve()==a.output.resolve():p.error('input and output must differ')
    run(a.input,a.output,a.seed,a.replay,not a.skip_sql)
if __name__=='__main__': main()
