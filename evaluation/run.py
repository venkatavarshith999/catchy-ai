"""Small synthetic regression set; not a held-out accuracy benchmark."""
import json
import os
from pathlib import Path
from llms.engine import analyze

def main():
    cases=json.loads(Path('evaluation/cases.json').read_text(encoding='utf-8-sig'))
    rows=[];tp=fp=fn=tn=0
    for case in cases:
        result=analyze(case['turns'])
        expected=case['expected']=='high'; predicted=result['level']=='high'
        tp+=expected and predicted;fp+=not expected and predicted
        fn+=expected and not predicted;tn+=not expected and not predicted
        rows.append({'id':case['id'],'expected':case['expected'],'actual':result['level'],'score':result['score'],'match':case['expected']==result['level']})
    report={'warning':'Synthetic development cases including known baseline gaps. NOT a generalization benchmark.', 'provider':os.environ.get('LLM_PROVIDER','rules'),'cases':len(cases),'true_positive':tp,'false_positive':fp,'false_negative':fn,'true_negative':tn,'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,'results':rows}
    Path('evaluation/results.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
