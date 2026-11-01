"""Dependencies require explicit ordering words in one source clause."""
import re


def extract_dependencies(actions, evidence):
    candidates = []
    for evidence_id, text in evidence:
        for sentence in re.split(r'[。；;\n]', text):
            matches = []
            for action in actions:
                quote = action.get('evidence_quotes', {}).get(evidence_id)
                if quote and sentence.count(quote) == 1:
                    matches.append((sentence.index(quote), quote, action['id']))
            matches.sort()
            for left, right in zip(matches, matches[1:]):
                between = sentence[left[0]+len(left[1]):right[0]]
                prefix = sentence[:left[0]]+left[1][:2]
                if re.search(r'然后|之后|再', between) and ('先' in prefix or re.search(r'完成|后', between)):
                    candidates.append({'before_action_id':left[2], 'after_action_id':right[2],
                                       'evidence_ids':[evidence_id], 'quote':sentence.strip(), 'origin':'document'})
    return candidates
