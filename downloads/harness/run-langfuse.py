"""Trace one explicitly scoped Claude Code run; never export reasoning or credentials."""
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid
import argparse

from dotenv import load_dotenv
from langfuse import Langfuse, propagate_attributes

P = Path(__file__).resolve().parent
ROOT = P
SECRETS = ROOT / '.runtime/langfuse.env'
load_dotenv(SECRETS)
required = ['LANGFUSE_PUBLIC_KEY', 'LANGFUSE_SECRET_KEY', 'LANGFUSE_BASE_URL']
if not all(os.environ.get(k) for k in required):
    raise SystemExit('Langfuse 연결 정보 미설정: .runtime/langfuse.env에 프로젝트 키와 주소를 직접 저장하세요. 키는 채팅에 보내지 마세요.')

registry = json.loads((P / 'source-registry.json').read_text(encoding='utf-8'))
names = {r['notebook_id']: 'NOTEBOOK_' + r['notebook'] for r in registry}
names.update({r['source_id']: r['notebook'] + ':' + r['id'] for r in registry})

def sanitize(value):
    """Keep public case/tool data; replace local identifiers and strip secret fields."""
    if isinstance(value, dict):
        return {k: sanitize(v) for k, v in value.items()
                if not re.search(r'(?i)cookie|csrf|secret|api.?key|authorization|signature|thinking', k)}
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    if isinstance(value, str):
        for key, alias in names.items():
            value = value.replace(key, alias)
        value = value.replace(str(ROOT), '[WORKSPACE]').replace(str(ROOT).replace('\\', '/'), '[WORKSPACE]')
        value = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[EMAIL]', value)
        value = re.sub(r'(?:sk-lf-|pk-lf-)[\w-]+', '[REDACTED_KEY]', value)
        return value[:18000]
    return value

def parse_result(block):
    content = block.get('content', [])
    texts = [content] if isinstance(content, str) else [x.get('text', '') for x in content if x.get('type') == 'text']
    for text in texts:
        try:
            return json.loads(text)
        except (ValueError, TypeError):
            pass
    return {'text': '\n'.join(texts)}

parser = argparse.ArgumentParser()
parser.add_argument('--repair', action='store_true', help='Requery C with an explicit source-boundary instruction')
parser.add_argument('--repair-v3', action='store_true', help='Requery C with absence-claim and alternative-path checks')
parser.add_argument('--repair-v4', action='store_true', help='Separate quoted rules from conditional reasoning and missing case facts')
options = parser.parse_args()
repair = options.repair or options.repair_v3 or options.repair_v4
version = 'v4' if options.repair_v4 else 'v3' if options.repair_v3 else 'v2' if repair else 'v1'
tag = ('LF-' + version + '-' if version in ('v3', 'v4') else 'LF-repair-' if repair else 'LF-live-') + datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
outdir = P / 'langfuse' / tag
outdir.mkdir(parents=True, exist_ok=False)
nb = json.loads((P / 'notebooks.json').read_text(encoding='utf-8'))
plan = {}
for role, doc in [('A', 'L276291'), ('B', 'Higdr000004'), ('C', 'L252747')]:
    row = next(x for x in registry if x['notebook'] == role and x['id'] == doc)
    plan[role] = {'notebook_id': nb[role]['id'], 'source_ids': [row['source_id']], 'document': row['title'], 'url': row['url']}
(outdir / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
rel = str(outdir.relative_to(P)).replace('\\', '/')
prompt = f'''공개자료를 사용하는 HUG 교육용 실제 실행입니다. 결과는 한국어로 작성합니다.
현재 폴더 CLAUDE.md와 {rel}/plan.json을 읽고 아래 실제 도구 시험을 순서대로 실행하라. 다른 계정·인증파일·다른 노트북에는 접근하지 않는다.
1. A를 지정한 source_ids로 notebook_query 하되 timeout=0.001, new_conversation=true로 한다. query는 "주택임대차보호법 제3조의3 제5항의 임차권등기 효과를 두 문장으로 설명하고 인용번호를 붙여 주세요."이다. 이것은 교육을 위해 의도적으로 극단적으로 짧은 시간제한을 넣는 실제 장애 주입 시험이며 자연 발생 장애라고 쓰지 않는다.
2. 오류 응답을 확인한 뒤 동일 A 질문·같은 source_ids를 timeout=60으로 한 번 재시도한다. 실제로 첫 호출이 성공했다면 오류를 만들거나 실패했다고 주장하지 말고 그 사실을 적는다.
3. B를 지정 source_ids, timeout=60, new_conversation=true로 실제 질의한다. 질문: "이 자료에 적힌 보증사고 발생 시 통지와 이행 청구 절차를 3문장으로 설명하고 각 문장에 인용번호를 붙여 주세요."
4. C를 지정 source_ids, timeout=60, new_conversation=true로 실제 질의한다. 질문: "임차권등기명령 절차에 관한 규칙 제4조에 적힌 명령 효력 발생 시점을 설명하고, 이 사실만으로 등기 완료나 이사 가능 여부를 확정할 수 있는지 구분해 주세요. 인용번호를 붙여 주세요."
5. 응답들의 실제 references와 source_ids를 확인하고 {rel}/review.md에 1500~2500자의 종합 검토 메모를 작성하라. 입력 사실이 없는 가상 질문에서 이사 가능 여부·가입·지급을 확정하지 말고, 명령의 효력과 등기 완료를 구분하라. 세 노트북별 짧은 인용 1개·원문 URL·미확인 사항, 장애 주입→실제 오류→재시도 결과를 넣는다.
6. {rel}/check.md에 시간제한 오류 복구 여부, 각 노트북 구조화 인용 수, 원문 사람 대조 미실시, 실행하지 않은 행위를 적는다. 원응답은 호스트 프로그램이 자동 기록하므로 대량으로 다시 옮겨 쓰지 않는다. 출력 파일 두 개만 작성한다. Bash·에이전트·공유·삭제·발송은 사용하지 않는다.
'''
if repair:
    prompt = f'''공개 교육용 C 응답의 인용 과대 귀속을 수정하는 실제 재시험이다. CLAUDE.md와 {rel}/plan.json을 읽어라.
원래 질문은 "임차권등기명령 절차에 관한 규칙 제4조에 적힌 명령 효력 발생 시점을 설명하고, 이 사실만으로 등기 완료나 이사 가능 여부를 확정할 수 있는지 구분해 주세요. 인용번호를 붙여 주세요."이다.
지침 v2 추가 절: 인용 문구가 실제로 말하는 범위와 모델의 일반 지식을 분리한다. 제공 규칙에 없는 이사·점유·주민등록 이전 조언에 그 규칙의 인용번호를 붙이지 않는다. 다른 법률의 근거가 필요한 주장은 "이 자료만으로 확인 불가; 다른 법률·개별 사실 확인 필요"로 남긴다. 등기 여부는 실제 등기 기록 없이는 확정하지 않는다.
C의 같은 source_ids에 timeout=60, new_conversation=true로 notebook_query를 실제 한 번 실행한다. query에는 원래 질문을 그대로 넣고 그 뒤 "[지침 v2]"와 위 추가 절을 붙여라. A/B 재조회나 추가 도구 호출은 하지 않는다.
실제 반환을 확인한 뒤 {rel}/review.md에 원래 질문, 바뀐 지침, 실제 새 응답의 근거 구절, 인용 과대 귀속 수정 여부, 남은 확인 사항을 적어라. {rel}/check.md에는 상태·references수·사람 법률 적용 검토 미실시를 적어라. 원응답은 프로그램이 기록하므로 다시 옮겨 쓰지 않는다. 두 파일만 작성한다. Bash·다른 에이전트·공유·삭제·발송은 하지 않는다.'''
if options.repair_v3:
    prompt = f'''공개 교육용 C 지침 v3 실제 재시험이다. CLAUDE.md와 {rel}/plan.json을 읽어라.
원래 질문: 임차권등기명령 절차에 관한 규칙 제4조에 적힌 명령 효력 발생 시점을 설명하고, 이 사실만으로 등기 완료나 이사 가능 여부를 확정할 수 있는지 구분해 주세요. 인용번호를 붙여 주세요.
지침 v3 추가 절:
1. 인용 구절에 없다는 사실과 규칙 전문에 규정이 없다는 주장을 구분한다. 전문 전체를 검사하지 않았으므로 "규칙에 이사·점유·주민등록 관련 규정이 없다/포함되지 않는다"고 단정하지 않는다. "이번에 제공된 인용 구절만으로 이사 가능 여부를 판단할 근거는 충분히 확인하지 못했다"고 범위를 한정한다. 제6조에 점유·주민등록 관련 기록사항이 있다는 점과 혼동하지 않는다.
2. 제4조 제3항의 두 효력 발생 경로를 각각 다룬다. (가) 임대인에게 결정이 송달되어 효력이 생겼다는 정보만 주어진 경우와 (나) 제5조 단서에 따른 등기가 되어 효력이 생겼다는 정보가 주어진 경우를 분리한다. (나)는 문언상 등기가 된 것을 전제로 하는 경로이므로 두 경우를 모두 "효력이 생겨도 등기 완료는 알 수 없다"로 묶지 않는다. (다) 경로 자체가 주어지지 않은 이번 질문에서는 어느 경로인지와 실제 등기기록을 추가 확인한다. 명령 효력과 등기 사실의 관계를 조건에 따라 설명하고 가상의 개별 사건에서 실제 완료됐다고 주장하지 않는다.
3. 이사 가능 여부·대항력 유지·지급 등은 별도 법률·개별 사실이 필요한 항목으로 분리한다. 해당 규칙 인용을 그런 판단의 근거로 과대 귀속하지 않는다. 효력 경로를 구분한 설명과 최종 개인 판단을 분리한다.
C의 같은 source_ids로 timeout=60,new_conversation=true인 notebook_query를 실제 1회만 호출한다. query에 원래 질문을 그대로 쓰고 그 뒤 "[지침 v3]"와 위 세 절을 붙여라. A/B나 다른 노트북은 조회하지 않는다.
실제 반환에서 세 절을 지켰는지 확인해 {rel}/review.md에 수정 전 문제/수정한 절/실제 응답의 짧은 구절/개선 여부/여전히 남은 문제를 적어라. {rel}/check.md에 상태,references 수,경로가/나/다 구분,부재 단정 여부,이사 판단 유보,사람 법률 적용 검토 미실시를 적어라. 실패가 남으면 그대로 적고 합격으로 꾸미지 않는다. 두 파일만 작성한다. 원응답은 호스트 프로그램이 기록한다. Bash·하위에이전트·공유·삭제·발송은 하지 않는다.'''
if options.repair_v4:
    prompt = f'''공개 교육용 C 지침 v4 재시험이다. CLAUDE.md와 {rel}/plan.json을 읽어라.
원래 질문: 임차권등기명령 절차에 관한 규칙 제4조에 적힌 명령 효력 발생 시점을 설명하고, 이 사실만으로 등기 완료나 이사 가능 여부를 확정할 수 있는지 구분해 주세요. 인용번호를 붙여 주세요.
지침 v4 추가 절:
출력은 다음 세 절로 나눈다. 1. 자료에서 확인한 문언: 제4조 제3항과 제5조 단서에 실제로 있는 짧은 원문 구절만 인용번호와 함께 적는다. 이 절에서만 출처번호를 사용한다. 2. 문언에 따른 조건부 설명: (가) 송달 정보만 주어진 경우, (나) 제5조 단서에 따른 등기가 되어 효력이 생겼다는 정보가 주어진 경우, (다) 경로가 미제공인 이번 질문을 따로 쓴다. 이 절은 앞 절 문언에 따른 AI의 조건부 설명으로 표시하며 출처번호를 추가하지 않는다. 3. 이번 사례의 미확인 사항: 이사·대항력 유지·지급은 다른 법률과 개별 사실 확인이 필요한 항목으로 남기며 출처번호를 추가하지 않는다.
전문 전체를 검사하지 않은 채 "규정이 없다/포함되지 않는다"고 단정하지 않는다. "이번에 제공된 인용 구절만으로 충분히 판단할 수 없음"처럼 확인 범위를 한정한다. 제6조의 점유·주민등록 기록사항과 이사 판단을 구분한다.
(가)의 이유는 송달 정보만으로 실제 등기 여부가 드러나지 않는다는 것이다. 송달 후에 촉탁·기입 절차가 반드시 남아 있다고 단정하지 않는다. 제5조 단서상 송달 전 촉탁 가능성이 있다.
(나)는 제시된 정보가 문언상 등기를 전제한다는 조건부 설명이다. 실제 등기기록을 열람해 확인 완료했다는 표현을 쓰지 않는다. (다)는 어느 경로인지와 실제 등기기록이 모두 미제공임을 밝힌다.
지침·답변 형식·AI가 해야 할 행동을 반복하는 문장을 답변에 넣지 않는다. 지침을 법령의 주장처럼 인용하지 않는다. 상담형 후속 제안으로 끝내지 않는다. 개별 사건의 등기·이사·승인·지급을 확정하지 않는다.
C의 같은 source_ids로 timeout=60,new_conversation=true인 notebook_query를 실제 한 번 호출한다. query에 원래 질문을 그대로 넣고 그 뒤 "[지침 v4]"와 위 추가 절을 붙여라. A/B 재조회와 다른 도구 호출은 하지 않는다.
실제 반환을 확인해 {rel}/review.md에 수정 전 문제, 고친 절, 새 응답의 짧은 구절, 남은 문제를 기록하고 {rel}/check.md에 실제 상태·인용수·세 절 형식·경로 분리·부재 단정·송달 후 절차 단정·실제확인 완료 오인·이사 판단 유보를 점검한다. 실패를 꾸미거나 숨기지 않는다. 두 파일만 작성한다. 원응답은 호스트 프로그램이 기록한다. Bash·에이전트·공유·삭제·발송은 하지 않는다.'''
lf = Langfuse(environment='hug-public-training', mask=lambda data, **_: sanitize(data))
if not lf.auth_check():
    raise SystemExit('Langfuse 인증 실패. 프로젝트·리전·키를 확인하세요. 키 값은 출력하지 않았습니다.')

args = [shutil.which('claude'), '-p', '--output-format', 'stream-json', '--verbose', '--strict-mcp-config', '--mcp-config', str(P / 'mcp-config.json'), '--tools', 'Read,Write,Edit', '--allowedTools', 'Read', 'Write', 'Edit', 'mcp__hug-notebooklm__notebook_query', '--permission-mode', 'dontAsk', '--effort', 'medium']
calls = {}
results = []
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
with propagate_attributes(session_id=tag, trace_name=f'HUG · C 지침 {version} 재시험' if repair else 'HUG · 세 노트북 조회와 오류 복구', tags=['HUG', 'public-only', 'live', 'instruction-' + version if repair else 'intentional-timeout-test']):
    with lf.start_as_current_observation(name='HUG · C 인용 범위 재시험' if repair else 'HUG · 세 노트북 조회와 재가공', as_type='agent', input={'scenario': '교육용 가상 공개자료 독해', 'notebooks': ['C'] if repair else ['A', 'B', 'C'], 'fault_injection': None if repair else 'A 최초 timeout=0.001s'}, metadata={'capture': 'Claude Code stream-json 실제 이벤트', 'reasoning_exported': False}) as root:
        trace_id = root.trace_id
        (outdir / 'trace.json').write_text(json.dumps({'trace_id': trace_id, 'url': lf.get_trace_url(trace_id=trace_id), 'session': tag, 'started_utc': started}, ensure_ascii=False, indent=2), encoding='utf-8')
        print('LANGFUSE_TRACE_STARTED', tag, flush=True)
        with (outdir / 'events.jsonl').open('w', encoding='utf-8') as log, (outdir / 'stderr.txt').open('w', encoding='utf-8') as err:
            proc = subprocess.Popen(args, cwd=P, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err, text=True, encoding='utf-8', errors='replace')
            proc.stdin.write(prompt)
            proc.stdin.close()
            for line in proc.stdout:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                message = event.get('message', {})
                blocks = message.get('content', []) if isinstance(message, dict) else []
                safe_blocks = [x for x in blocks if x.get('type') != 'thinking']
                if isinstance(message, dict):
                    message['content'] = safe_blocks
                if event.get('subtype') == 'thinking_tokens':
                    continue
                log.write(json.dumps(event, ensure_ascii=False) + '\n')
                log.flush()
                for block in safe_blocks:
                    if block.get('type') == 'tool_use':
                        name = block['name']
                        tool_input = block.get('input', {})
                        role = next((r for r, v in plan.items() if v['notebook_id'] == tool_input.get('notebook_id')), None)
                        display = f'노트북 {role} 조회' if role else name
                        if tool_input.get('timeout') == 0.001:
                            display += ' · 의도적 시간제한 시험'
                        if name.startswith('mcp__') or name in ('Write', 'Edit'):
                            span = root.start_observation(name=display, as_type='tool', input=sanitize(tool_input))
                            calls[block['id']] = (span, name, tool_input)
                            print('TOOL_START', display, flush=True)
                    elif block.get('type') == 'tool_result' and block.get('tool_use_id') in calls:
                        span, name, tool_input = calls.pop(block['tool_use_id'])
                        data = parse_result(block)
                        failed = block.get('is_error') or data.get('status') == 'error'
                        span.update(output=sanitize(data), level='ERROR' if failed else 'DEFAULT', status_message='실제 오류 응답' if failed else '도구 응답 수신')
                        span.end()
                        if name.endswith('notebook_query'):
                            refs = data.get('references', [])
                            gate = root.start_observation(name='근거 검사 · 인용 목록 확인', as_type='guardrail', input={'status': data.get('status'), 'references': len(refs)})
                            passed = not failed and bool(refs)
                            gate.update(output={'passed': passed, 'meaning': '구조화 인용 존재 검사; 법적 정확도 인증 아님'}, level='DEFAULT' if passed else 'WARNING')
                            gate.end()
                            results.append({'input': tool_input, 'response': data, 'citation_gate_passed': passed})
                            print('QUERY_RESULT', data.get('status'), 'citations', len(refs), flush=True)
                if event.get('type') == 'result':
                    print('CLAUDE_RESULT', event.get('subtype'), flush=True)
            code = proc.wait()
        for span, _, _ in calls.values():
            span.update(level='ERROR', status_message='반환 기록 없이 종료')
            span.end()
        root.update(output={'exit_code': code, 'queries': len(results), 'citation_passes': sum(x['citation_gate_passed'] for x in results), 'report': 'review.md', 'fault_test_is_intentional': not repair})
        root.set_trace_io(input={'scenario': 'HUG 공개자료 · A/B/C 조회와 가상 사례 재가공'}, output={'exit_code': code, 'queries': len(results), 'citation_passes': sum(x['citation_gate_passed'] for x in results)})
lf.flush()
(outdir / 'actual-results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
(outdir / 'process.json').write_text(json.dumps({'exit_code': code, 'started_utc': started, 'finished_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'trace_id': trace_id}, indent=2), encoding='utf-8')
print('DONE', str(outdir), flush=True)
raise SystemExit(code)
